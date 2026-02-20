[![version](https://img.shields.io/github/manifest-json/v/stephen-kim/ha-navien-smart?filename=custom_components%2Fnavien_smart%2Fmanifest.json)](https://github.com/stephen-kim/ha-navien-smart/releases/latest)
[![issues](https://img.shields.io/github/issues/stephen-kim/ha-navien-smart)](https://github.com/stephen-kim/ha-navien-smart/issues)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

# Navien Smart for Home Assistant

A Home Assistant custom integration for controlling Navien Smart heating mats.

English | [한국어](https://github.com/stephen-kim/ha-navien-smart/blob/latest/README-ko.md)

![demo](https://raw.githubusercontent.com/kyle-seongwoo-jun/homebridge-navien-smart/latest/docs/demo.jpg)

## Features

- Provides `climate` entities for heating mats
- Supports dual-zone left/right split mode for supported devices (`separate_control`)
- Real-time status updates via AWS IoT MQTT
- `sound_enabled`: use operation beep on supported devices
- `scan_interval`: coordinator polling interval (seconds)
- MQTT state synchronization
  - Uses AWS IoT MQTT (WebSocket) real-time updates by default
  - Automatically falls back to REST polling if MQTT connection fails
  - In fallback mode, `scan_interval` directly affects status update latency
  - Even when MQTT is healthy, `scan_interval` is used as a watchdog for session refresh/recovery

## Installation

1. Install the Navien app on your smartphone, sign up, and complete device pairing at least once.
2. Install [HACS](https://www.hacs.xyz) in Home Assistant.
3. Open HACS in Home Assistant.
4. Go to `Integrations` -> top-right menu -> `Custom repositories`.
5. Add this repository URL and select `Integration` as the category.
6. Search for `Navien Smart` and install it.
7. Restart Home Assistant.
8. Go to `Settings` -> `Devices & Services` -> `Add Integration` -> select `Navien Smart`.

Shortcut:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stephen-kim&repository=ha-navien-smart)

## Notes

- This integration uses an unofficial API (based on reverse engineering).
- This plugin has only been tested with `EME520` and `EMW720` models.
- Supported models are limited, and behavior may vary by device/firmware.
- The previous Homebridge implementation was removed from this repository; it is now Python/HA-only.

## Post-install Setup

`Settings` -> `Devices & Services` -> `Integrations` -> `Add Integration` -> search for `Navien Smart`

Or:

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=navien_smart)

### Auth modes (choose one)

- `account` (recommended for first setup)
  - Inputs: `username`, `password`
- `token`
  - Inputs: `username`, `refresh_token`, `account_seq`
  - Use this if you do not want to store your password in Home Assistant

## Development

Integration source path:

- `custom_components/navien_smart`

Validation workflows:

- `.github/workflows/validate.yml`
- `.github/workflows/hassfest.yml`
