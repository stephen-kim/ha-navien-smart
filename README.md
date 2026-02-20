[![version](https://img.shields.io/github/manifest-json/v/stephen-kim/ha-navien-smart?filename=custom_components%2Fnavien_smart%2Fmanifest.json)](https://github.com/stephen-kim/ha-navien-smart/releases/latest)
[![releases](https://img.shields.io/github/downloads/stephen-kim/ha-navien-smart/total)](https://github.com/stephen-kim/ha-navien-smart/releases)
[![issues](https://img.shields.io/github/issues/stephen-kim/ha-navien-smart)](https://github.com/stephen-kim/ha-navien-smart/issues)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

# Navien Smart for Home Assistant

Home Assistant custom integration for controlling Navien Smart heating mats.

English | [한국어](https://github.com/stephen-kim/ha-navien-smart/blob/latest/README-ko.md)

![demo](https://raw.githubusercontent.com/kyle-seongwoo-jun/homebridge-navien-smart/latest/docs/demo.jpg)

## Features

- Config flow support (`Settings` -> `Devices & Services` -> `Add Integration`)
- Auth modes
  - `account`: username + password
  - `token`: username + refresh token + account sequence
- Climate entities for heating mats
- Dual-zone split mode (`separate_control`) for supported devices
- Real-time status updates through AWS IoT MQTT

## Installation

### Method 1: HACS

1. Open HACS.
2. Go to `Integrations` -> menu -> `Custom repositories`.
3. Add this repository URL with category `Integration`.
4. Search for `Navien Smart` and install.
5. Restart Home Assistant.
6. Add integration: `Settings` -> `Devices & Services` -> `Add Integration` -> `Navien Smart`.

Or use this shortcut:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stephen-kim&repository=ha-navien-smart)

### Method 2: Manual install (Samba / SFTP)

Copy `custom_components/navien_smart` into your Home Assistant `custom_components` directory.

### Method 3: Shell install (SSH / Terminal)

```shell
wget -q -O - https://raw.githubusercontent.com/stephen-kim/ha-navien-smart/latest/install.sh | bash -
```

Specific version:

```shell
wget -q -O - https://raw.githubusercontent.com/stephen-kim/ha-navien-smart/latest/install.sh | ARCHIVE_TAG=v0.1.3 bash -
```

After installation, restart Home Assistant.

## Integration Options

- `auth_mode`: `account` or `token`
- `separate_control`: split left/right entities for dual-zone devices
- `sound_enabled`: enable operation beep for supported models
- `scan_interval`: coordinator polling interval in seconds

### MQTT behavior

- Real-time state sync uses AWS IoT MQTT over WebSocket by default.
- If MQTT startup fails, the integration automatically falls back to REST polling mode.
- In fallback mode, `scan_interval` directly affects status update latency.
- Even when MQTT is healthy, `scan_interval` is still used as a watchdog for session refresh/recovery.  
  If real-time is stable in your environment, consider a higher value (for example `180`-`300`) to reduce API calls.

## Notes

- This integration uses an unofficial API based on reverse engineering.
- This plugin is only tested with `EME520` and `EMW720` models.
- Supported models are still limited. Behavior may vary by device/firmware.
- The original Homebridge implementation in this repository has been removed. This repository is now Python/HA focused.

## Configure

`Settings` -> `Devices & Services` -> `Integrations` -> `Add Integration` -> Search `Navien Smart`

Or use:

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=navien_smart)

### Auth modes

- `account` (recommended for first setup)
  - Input: `username`, `password`
- `token`
  - Input: `username`, `refresh_token`, `account_seq`
  - Use this when you do not want to keep a password in Home Assistant

### Recommended options

- `separate_control`
  - Enable for dual-zone models to create left/right climate entities separately
- `sound_enabled`
  - Enable operation beep on supported devices
- `scan_interval`
  - Coordinator refresh interval in seconds (default: `120`)

## Development

Main integration path:

- `custom_components/navien_smart`

Validation workflows:

- `.github/workflows/validate.yml`
- `.github/workflows/hassfest.yml`
