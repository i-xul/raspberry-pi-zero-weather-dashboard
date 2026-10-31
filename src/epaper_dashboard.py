
#!/usr/bin/env python3
"""Pi Zero W e-paper dashboard with COSY BARO and DHT22 measurements."""

import argparse
import json
import logging
import math
import os
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

import requests
from PIL import Image, ImageDraw, ImageFont

from dashboard_config import load_config

CONFIG = load_config()
COSY_BARO_URL = CONFIG["cosy_baro_url"]
DHT22_URL = CONFIG["dht22_url"]

DHT22_STATE_FILE = Path(
    CONFIG["dht22_cache_path"]
)

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
COSY_BARO_STALE_AFTER = timedelta(minutes=15)
DHT22_CACHE_MAX_AGE = timedelta(hours=24)

DISPLAY_WIDTH = 400
DISPLAY_HEIGHT = 300

logging.basicConfig(
    stream=sys.stdout,
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)


def run_cmd(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True, timeout=25
        ).strip()
    except Exception as exc:
        logging.warning("Command failed: %r: %s", cmd, exc)
        return "N/A"


def cpu_temp():
    return run_cmd("vcgencmd measure_temp").replace("temp=", "")


def ip_addr():
    output = run_cmd("hostname -I")
    return output.split()[0] if output and output != "N/A" else "N/A"


def load_last_good():
    """Return a valid DHT22 cache measurement younger than 24 hours."""
    try:
        data = json.loads(DHT22_STATE_FILE.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            return None

        temperature = float(data["temperature"])
        humidity = float(data["humidity"])
        updated = datetime.fromisoformat(data["updated"])

        if not all(math.isfinite(v) for v in (temperature, humidity)):
            return None

        if not 0 <= humidity <= 100:
            return None

        if updated.tzinfo is None or updated.utcoffset() is None:
            return None

        age = datetime.now(timezone.utc) - updated.astimezone(timezone.utc)

        if not timedelta(0) <= age < DHT22_CACHE_MAX_AGE:
            return None

        return {
            "temperature": temperature,
            "humidity": humidity,
            "updated": data["updated"],
        }

    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None


def save_last_good(data):
    temp_path = DHT22_STATE_FILE.with_suffix(".tmp")
    try:
        temp_path.write_text(json.dumps(data), encoding="utf-8")
        os.replace(temp_path, DHT22_STATE_FILE)
    except OSError as exc:
        logging.warning("Could not save DHT22 state: %s", exc)
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def fetch_dht22():
    last_good = load_last_good()
    try:
        response = requests.get(DHT22_URL, timeout=(5, 12))
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") != "ok":
            raise ValueError("Sensor status is not ok")

        temperature = float(payload["temperature"])
        humidity = float(payload["humidity"])

        if not (math.isfinite(temperature) and math.isfinite(humidity)):
            raise ValueError("Non-finite sensor value")
        if not (0 <= humidity <= 100):
            raise ValueError("Humidity out of range")

        data = {
            "temperature": temperature,
            "humidity": humidity,
            "updated": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        }
        save_last_good(data)
        return data, True

    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logging.warning("DHT22 request failed: %s", exc)
        return last_good, False


def fetch_cosy_baro():
    try:
        with urlopen(COSY_BARO_URL, timeout=10) as response:
            payload = json.load(response)

        temperature = float(payload["temperature_c"])
        humidity = float(payload["humidity_percent"])
        pressure = float(payload["pressure_hpa"])
        updated = datetime.fromisoformat(payload["received_at"])

        if not all(
            math.isfinite(value)
            for value in (temperature, humidity, pressure)
        ):
            raise ValueError("Non-finite COSY BARO value")

        if not 0 <= humidity <= 100:
            raise ValueError("Humidity out of range")

        return {
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure,
            "updated": updated,
        }, True

    except (OSError, ValueError, KeyError, TypeError) as exc:
        logging.warning("COSY BARO request failed: %s", exc)
        return None, False


def cosy_baro_status(cosy, api_ok):
    if not api_ok or not cosy:
        return "OFFLINE"

    updated = cosy["updated"]

    if updated.tzinfo is None or updated.utcoffset() is None:
        logging.warning("COSY BARO timestamp has no timezone")
        return "STALE"

    age = datetime.now(timezone.utc) - updated.astimezone(timezone.utc)

    if age < timedelta(0):
        logging.warning("COSY BARO timestamp is in the future")
        return "STALE"

    if age >= COSY_BARO_STALE_AFTER:
        return "STALE"

    return "ONLINE"


def draw_box(draw, xy, title, lines, font, title_font):
    x1, y1, x2, y2 = xy
    draw.rectangle(xy, outline=0)
    draw.text((x1 + 8, y1 + 5), title, font=title_font, fill=0)

    y = y1 + 24
    for line in lines:
        if y > y2 - 12:
            break
        draw.text((x1 + 8, y), line, font=font, fill=0)
        y += 15


def render_dashboard():
    cosy, cosy_ok = fetch_cosy_baro()
    sensor, sensor_ok = fetch_dht22()
    load1, load5, _ = os.getloadavg()

    image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 255)
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype(FONT_REGULAR, 12)
    title_font = ImageFont.truetype(FONT_BOLD, 17)
    big_font = ImageFont.truetype(FONT_BOLD, 33)
    label_font = ImageFont.truetype(FONT_REGULAR, 13)
    header_font = ImageFont.truetype(FONT_BOLD, 15)
    time_font = ImageFont.truetype(FONT_REGULAR, 11)

    # Header: retained from the existing infrastructure monitor.
    draw.text((10, 8), "Pi Zero W Monitor", font=header_font, fill=0)

    if sensor:
        try:
            stamp = datetime.fromisoformat(
                sensor["updated"]
            ).strftime("%d.%m.%Y %H:%M")
        except (ValueError, TypeError):
            stamp = "UNKNOWN"
    else:
        stamp = "NO DATA"

    stamp_width = draw.textbbox((0, 0), stamp, font=time_font)[2]
    draw.text(
        (DISPLAY_WIDTH - 10 - stamp_width, 9),
        stamp,
        font=time_font,
        fill=0,
    )
    draw.line((10, 28, DISPLAY_WIDTH - 10, 28), fill=0)

    # DISPLAY NODE: retained from the existing infrastructure monitor.
    draw_box(
        draw,
        (10, 38, 390, 85),
        "DISPLAY NODE",
        [
            f"{socket.gethostname()}  {ip_addr()}  "
            f"Temp {cpu_temp()}  Load {load1:.2f}/{load5:.2f}",
        ],
        font,
        title_font,
    )

    # KEITTIÖ: COSY BARO replaces the former PI 5 SERVER section.
    draw.rectangle((10, 95, 390, 180), outline=0)
    draw.text((18, 100), "KEITTIÖ", font=title_font, fill=0)
    draw.text(
        (308, 103),
        cosy_baro_status(cosy, cosy_ok),
        font=font,
        fill=0,
    )

    draw.text((18, 125), "LÄMPÖTILA", font=label_font, fill=0)
    draw.text((155, 125), "KOSTEUS", font=label_font, fill=0)
    draw.text((280, 125), "PAINE hPa", font=label_font, fill=0)

    if cosy:
        temperature = f"{cosy['temperature']:.1f} C"
        humidity = f"{cosy['humidity']:.0f} %"
        pressure = f"{cosy['pressure']:.1f}"
    else:
        temperature = "--.- C"
        humidity = "-- %"
        pressure = "----.-"

    draw.text((18, 145), temperature, font=title_font, fill=0)
    draw.text((155, 145), humidity, font=title_font, fill=0)
    draw.text((280, 145), pressure, font=title_font, fill=0)

    # OLOHUONE / DHT22: original rendering, only title changed.
    draw.rectangle((10, 190, 390, 295), outline=0)
    draw.text((18, 195), "OLOHUONE / DHT22", font=title_font, fill=0)
    draw.text(
        (292, 199),
        "ONLINE" if sensor_ok else (
            "STALE" if sensor else "OFFLINE"
        ),
        font=font,
        fill=0,
    )
    draw.line((200, 223, 200, 285), fill=0)
    draw.text((22, 222), "LAMPOTILA", font=label_font, fill=0)
    draw.text((213, 222), "KOSTEUS", font=label_font, fill=0)

    if sensor:
        draw.text(
            (20, 241),
            f"{sensor['temperature']:.1f} C",
            font=big_font,
            fill=0,
        )
        draw.text(
            (211, 241),
            f"{sensor['humidity']:.1f} %",
            font=big_font,
            fill=0,
        )
    else:
        draw.text((20, 241), "--.- C", font=big_font, fill=0)
        draw.text((211, 241), "--.- %", font=big_font, fill=0)

    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Save a PNG preview without accessing the e-paper display",
    )
    args = parser.parse_args()

    image = render_dashboard()

    if args.preview:
        preview_path = Path("weather_dashboard_preview.png")
        image.save(preview_path)
        print(f"Preview saved: {preview_path.resolve()}")
        return

    # Import the existing working Waveshare driver only for display mode.
    sys.path.append(CONFIG["waveshare_lib_path"])
    from waveshare_epd import epd4in2

    epd = epd4in2.EPD()
    epd.init()
    epd.display(epd.getbuffer(image))
    epd.sleep()


if __name__ == "__main__":
    main()
