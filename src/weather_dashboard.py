
#!/usr/bin/env python3
"""Weather dashboard for the Raspberry Pi Zero W."""

import json
from urllib.request import urlopen

from dashboard_config import load_config

API_URL = load_config()["cosy_baro_url"]
REQUEST_TIMEOUT = 10


def fetch_weather():
    """Fetch the latest COSY BARO measurement from Raspberry Pi 4."""
    with urlopen(API_URL, timeout=REQUEST_TIMEOUT) as response:
        data = json.load(response)

    required_fields = (
        "temperature_c",
        "humidity_percent",
        "pressure_hpa",
        "received_at",
    )

    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing field in API response: {field}")

    return data


def main():
    try:
        weather = fetch_weather()
    except (OSError, ValueError) as error:
        print(f"Failed to fetch weather data: {error}")
        return

    print("COSY BARO weather data")
    print(f"Temperature: {weather['temperature_c']} °C")
    print(f"Humidity:    {weather['humidity_percent']} %")
    print(f"Pressure:    {weather['pressure_hpa']} hPa")
    print(f"Updated:     {weather['received_at']}")


if __name__ == "__main__":
    main()
