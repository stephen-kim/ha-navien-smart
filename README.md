# Navien Smart for Home Assistant

Home Assistant custom integration for controlling Navien Smart heating mats.

## Features

- Config flow support (`Settings` -> `Devices & Services` -> `Add Integration`)
- Auth modes
  - `account`: username + password
  - `token`: username + refresh token + account sequence
- Climate entities for heating mats
- Dual-zone split mode (`separate_control`) for supported devices
- Real-time status updates through AWS IoT MQTT

## Install (HACS)

1. Open HACS.
2. Go to `Integrations` -> menu -> `Custom repositories`.
3. Add this repository URL with category `Integration`.
4. Search for `Navien Smart` and install.
5. Restart Home Assistant.
6. Add integration: `Settings` -> `Devices & Services` -> `Add Integration` -> `Navien Smart`.

## Integration Options

- `auth_mode`: `account` or `token`
- `separate_control`: split left/right entities for dual-zone devices
- `sound_enabled`: enable operation beep for supported models
- `scan_interval`: coordinator polling interval in seconds

## Notes

- This integration uses an unofficial API based on reverse engineering.
- Supported models are still limited. Behavior may vary by device/firmware.
- The original Homebridge implementation in this repository has been removed. This repository is now Python/HA focused.

## Development

Main integration path:

- `custom_components/navien_smart`

Validation workflows:

- `.github/workflows/validate.yml`
- `.github/workflows/hassfest.yml`
