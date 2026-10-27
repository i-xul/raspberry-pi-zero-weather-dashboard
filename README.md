# Raspberry Pi Zero W Weather Dashboard

An e-paper weather dashboard powered by a Raspberry Pi Zero W and a Waveshare 4.2-inch display.

The dashboard retrieves indoor weather measurements from a Raspberry Pi 4 over a local HTTP API and displays temperature, relative humidity, and atmospheric pressure.

## Project architecture

The system consists of two Raspberry Pi devices:

**Raspberry Pi 4 — Weather sensor receiver**
- Receives 868 MHz radio transmissions using an RTL-SDR USB receiver.
- Decodes measurements from a TFA Dostmann WeatherHub COSY BARO (35.1154.01) sensor.
- Collects and stores the latest measurement.
- Provides the measurement through a local HTTP API.

**Raspberry Pi Zero W — E-paper dashboard**
- Retrieves measurements from the Raspberry Pi 4 over Wi-Fi.
- Displays temperature, humidity, and atmospheric pressure on a Waveshare 4.2-inch e-paper display.
- Will support automatic refreshes and recovery from temporary network failures.

The Zero W application is under development.

## Data flow

```text
TFA COSY BARO sensor
        |
        | 868.250 MHz radio
        v
RTL-SDR receiver
        |
        v
Raspberry Pi 4
  tfrec decoder
        |
        v
Python measurement collector
        |
        v
Local HTTP API
        |
        | Wi-Fi / LAN
        v
Raspberry Pi Zero W
        |
        v
Waveshare 4.2" e-paper display
```

## COSY BARO receiver development

The TFA WeatherHub COSY BARO sensor was not supported by the original receiver configuration used for this project. Initial attempts to decode its transmissions with `rtl_433` were unsuccessful.

The receiver implementation was therefore developed using the existing [baycom/tfrec](https://github.com/baycom/tfrec) project as its foundation.

The original `tfrec` software was developed by **Georg Acher and Deti Fliegl**. Their work provides the RTL-SDR reception and WeatherHub protocol infrastructure on which the COSY BARO extension depends.

The project-specific extension adds support for WeatherHub message type `0x18`, including the CRC32 initialization value `0xCA0ABB08`, measurement decoding, JSON output, duplicate-frame suppression, and a Python-based measurement collection and HTTP API layer.

The modified receiver and its technical documentation are available here:

**[i-xul/tfrec — feature/cosy-baro](https://github.com/i-xul/tfrec/tree/feature/cosy-baro)**

The receiver remains a separate project and retains its original GPLv2 licensing and copyright notices.

## HTTP API

The Raspberry Pi 4 currently exposes the latest measurement at:

`http://192.0.2.10:8765/api/cosy-baro`

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

The endpoint is intended for use on the trusted local network. It does not currently provide authentication or TLS encryption.

## Project status

The Raspberry Pi 4 receiver, measurement collector, HTTP API, and systemd services are operational.

The Raspberry Pi Zero W dashboard, display rendering, automatic updates, and deployment configuration are planned development work.

## Hardware

- Raspberry Pi Zero W
- Waveshare 4.2-inch e-paper display
- Raspberry Pi 4
- RTL-SDR USB receiver
- TFA Dostmann WeatherHub COSY BARO 35.1154.01

## Documentation

Additional setup, architecture, and deployment documentation will be added as the Zero W implementation progresses.

## Credits

The COSY BARO receiver extension is based on [tfrec by Georg Acher and Deti Fliegl](https://github.com/baycom/tfrec). The original authors retain credit for their software and protocol implementation.

This repository contains the separate Raspberry Pi Zero W dashboard application, not a replacement for the original receiver software.
