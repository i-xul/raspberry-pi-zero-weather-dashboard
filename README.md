# Raspberry Pi Zero W Weather Dashboard

An operational e-paper weather and system monitoring dashboard built with a Raspberry Pi Zero W and a Waveshare 4.2-inch monochrome display.

The dashboard combines indoor environmental measurements from two sources with basic Raspberry Pi system information. It refreshes automatically, detects stale COSY BARO measurements, and continues running after individual refresh failures.

## Features

- Temperature, relative humidity, and atmospheric pressure from a TFA Dostmann WeatherHub COSY BARO sensor.
- Living room temperature and humidity from a DHT22 sensor.
- Raspberry Pi Zero W hostname, IP address, CPU temperature, and system load.
- Automatic e-paper refreshes with a five-minute delay between refresh cycles.
- COSY BARO measurement freshness monitoring.
- DHT22 last-known-good measurement fallback.
- Error logging and a 120-second timeout for each display refresh.
- systemd-managed background operation.
- PNG preview mode for checking the display layout without updating the e-paper panel.

## Project architecture

The system uses two Raspberry Pi devices for COSY BARO reception and display, plus a separate HTTPS endpoint for the DHT22 measurements.

### Raspberry Pi 4 — Weather sensor receiver

- Receives 868 MHz transmissions through an RTL-SDR USB receiver.
- Decodes TFA Dostmann WeatherHub COSY BARO (35.1154.01) messages using a modified `tfrec` receiver.
- Collects the latest decoded measurements.
- Exposes temperature, humidity, pressure, and the reception timestamp through a local HTTP API.

### Raspberry Pi Zero W — E-paper dashboard

- Retrieves COSY BARO measurements from the Raspberry Pi 4 over the local network.
- Retrieves DHT22 measurements from a separate HTTPS API.
- Renders measurements and system information on the Waveshare 4.2-inch e-paper display.
- Checks COSY BARO measurement freshness using the source timestamp.
- Stores the last successfully retrieved DHT22 values for fallback use.
- Runs continuously through a systemd-managed refresh loop.

## Data flow

```text
TFA COSY BARO (868.250 MHz)
          |
          v
    RTL-SDR receiver
          |
          v
     Raspberry Pi 4
    Modified tfrec
          |
          v
  Measurement collector
          |
          v
 Local HTTP API :8765
          |
          +----------------------+
                                 |
DHT22 HTTPS API -----------------+--> Raspberry Pi Zero W
                                 |      |
                                 |      v
                                 |  Python dashboard
                                 |      |
                                 |      v
                                 +--> Waveshare 4.2" e-paper
```

The Zero W also reads local system information for the display node section.

## Hardware

- Raspberry Pi Zero W
- Waveshare 4.2-inch monochrome e-paper display (Rev 2.1, 400 × 300)
- Raspberry Pi 4
- RTL-SDR USB receiver
- TFA Dostmann WeatherHub COSY BARO 35.1154.01
- DHT22 sensor connected to a separately hosted measurement service

## Software structure

```text
raspberry-pi-zero-weather-dashboard/
├── .gitignore
├── README.md
└── src/
    ├── dashboard_loop.py
    ├── epaper_dashboard.py
    └── weather_dashboard.py
```

### `src/epaper_dashboard.py`

The main dashboard application.

It retrieves sensor data, validates measurements, determines sensor status, renders the dashboard using Pillow, and sends the resulting image to the Waveshare display.

It also supports a preview mode:

```bash
python3 src/epaper_dashboard.py --preview
```

Preview mode saves `weather_dashboard_preview.png` in the current working directory without initializing or updating the e-paper display. Sensor API requests are still performed.

### `src/dashboard_loop.py`

Runs the dashboard repeatedly using a subprocess.

Each refresh has a maximum runtime of 120 seconds. The loop records successful refreshes, nonzero exit codes, timeouts, and process startup failures.

After each attempt, the loop sleeps for 300 seconds before starting another refresh.

### `src/weather_dashboard.py`

A lightweight command-line utility for testing the COSY BARO API independently of the e-paper display.

```bash
python3 src/weather_dashboard.py
```

It retrieves and prints the latest COSY BARO temperature, humidity, pressure, and reception timestamp.

## Sensor status indicators

### COSY BARO — Kitchen

The dashboard uses the `received_at` timestamp provided by the Raspberry Pi 4 API to determine measurement freshness.

| Status | Meaning |
|---|---|
| `ONLINE` | The API responds successfully and the measurement is less than 15 minutes old. |
| `STALE` | The API responds, but the measurement is at least 15 minutes old or has an invalid timezone/future timestamp. |
| `OFFLINE` | The API request fails or the returned measurement is invalid. |

When the measurement is stale, the last values returned by the API remain visible alongside the `STALE` indicator.

If the API request fails, the current implementation displays unavailable values instead of a locally cached COSY BARO measurement.

### DHT22 — Living room

The DHT22 section uses a separate HTTPS endpoint.

| Status | Meaning |
|---|---|
| `ONLINE` | The latest API request succeeded and returned valid measurements. |
| `STALE` | The request failed, but a previously saved valid measurement is available. |
| `OFFLINE` | The request failed and no saved measurement is available. |

The DHT22 status is based on request success and fallback availability. Cached measurements must be less than 24 hours old, have valid numeric values, and contain a timezone-aware timestamp. Older or invalid cached measurements are discarded.

The last successfully retrieved DHT22 values are stored locally at:

```text
/home/pi/waveshare_epaper/dht22_last_good.json
```

## HTTP APIs

### COSY BARO

The Raspberry Pi 4 exposes the latest measurement at:

```text
http://192.0.2.10:8765/api/cosy-baro
```

Example response:

```json
{
  "sensor": "TFA COSY BARO",
  "id": "183625388a34",
  "temperature_c": 23.9,
  "humidity_percent": 53,
  "pressure_hpa": 1020.6,
  "received_at": "2026-10-27T21:54:00+02:00"
}
```

The endpoint is intended for use on a trusted local network. It does not currently provide authentication or TLS encryption.

The IP address is specific to the current deployment.

### DHT22

The dashboard retrieves DHT22 measurements from:

```text
https://sensor.example.com/api/lab_temp
```

The application expects an API response with a successful `status` value and numeric `temperature` and `humidity` fields.

## Deployment and operation

The current installation runs on Raspberry Pi OS Bullseye (32-bit) with Python 3.

The dashboard uses Pillow for image rendering, Requests for the DHT22 API, and the existing Waveshare Python driver for the physical display.

The Waveshare driver is imported from:

```text
/home/pi/waveshare_epaper/lib
```

The current installation uses the following systemd service:

```text
epaper-dashboard.service
```

The service runs the dashboard refresh loop in the background.

Check the service status:

```bash
sudo systemctl status epaper-dashboard.service
```

View recent refresh logs:

```bash
sudo journalctl -u epaper-dashboard.service -n 30 --no-pager
```

Follow logs in real time:

```bash
sudo journalctl -u epaper-dashboard.service -f
```

The refresh loop records successful updates and failures. A failed refresh does not terminate the loop under normal handled error conditions.

The application has been tested recovering after power interruptions, although this does not guarantee recovery from every possible power or storage failure.

### Updating the application

Development is performed locally on Windows using VSCodium.

Changes are committed and pushed to GitHub, then retrieved on the Raspberry Pi Zero W.

```bash
cd ~/raspberry-pi-zero-weather-dashboard
git pull --ff-only
```

The refresh loop launches `epaper_dashboard.py` as a new Python process for each update, so changes to that file are normally picked up on the next cycle.

Changes to `dashboard_loop.py` itself require restarting the running loop to take effect.

## COSY BARO receiver development

The TFA WeatherHub COSY BARO sensor was not supported by the original receiver configuration used for this project. Initial attempts to decode its transmissions with `rtl_433` were unsuccessful.

The receiver implementation was therefore developed using the existing [baycom/tfrec](https://github.com/baycom/tfrec) project as its foundation.

The original `tfrec` software was developed by **Georg Acher and Deti Fliegl**. Their work provides the RTL-SDR reception and WeatherHub protocol infrastructure on which the COSY BARO extension depends.

The project-specific extension adds support for WeatherHub message type `0x18`, including the CRC32 initialization value `0xCA0ABB08`, measurement decoding, JSON output, duplicate-frame suppression, and a Python-based measurement collection and HTTP API layer.

The modified receiver and its technical documentation are available here:

**[i-xul/tfrec — feature/cosy-baro](https://github.com/i-xul/tfrec/tree/feature/cosy-baro)**

The receiver remains a separate project and retains its original GPLv2 licensing and copyright notices.

## Current project status

The dashboard is operational.

Implemented functionality includes:

- COSY BARO reception and local HTTP API on Raspberry Pi 4.
- COSY BARO and DHT22 measurement display on Raspberry Pi Zero W.
- Raspberry Pi Zero W system information.
- Automatic e-paper updates.
- COSY BARO measurement-age monitoring.
- DHT22 last-known-good fallback.
- Refresh timeout and error logging.
- systemd-managed background execution.
- PNG preview generation.

Potential future improvements include more comprehensive API failure recovery, additional automated tests, configuration management, and expanded deployment documentation.

## Credits

The COSY BARO receiver extension is based on [tfrec by Georg Acher and Deti Fliegl](https://github.com/baycom/tfrec). The original authors retain credit for their software and protocol implementation.

This repository contains the separate Raspberry Pi Zero W dashboard application, not a replacement for the original receiver software.

## Local configuration

The dashboard reads deployment-specific settings from
`config.local.json` in the repository root.

Copy `config.example.json` to `config.local.json` and configure:

- `cosy_baro_url`: COSY BARO receiver API endpoint
- `dht22_url`: DHT22 sensor API endpoint
- `dht22_cache_path`: local cache for the last valid DHT22 reading
- `waveshare_lib_path`: Waveshare Python driver library directory

`config.local.json` is excluded from Git and must not be committed.

The configuration file must be present on the Raspberry Pi Zero W
before starting the dashboard service.
