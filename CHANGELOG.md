# Changelog

## 0.1.8

- Fixed setup crash (`KeyError: 'navien_smart'`) during config entry setup/reload
- Added defensive domain-data guards in setup/unload lifecycle

## 0.1.7

- Fixed potential setup failure when enabling separate left/right control on some models
- Hardened nickname parsing for dual-zone metadata (supports alternate API shape and non-string values)

## 0.1.6

- Added detailed setup descriptions for account/token fields in config flow
- Added guidance about model-dependent dual-zone control and operation beep support
- Added option-screen descriptions for separate control, beep, and scan interval

## 0.1.5

- Fixed device setup failure when heat-control values include unit suffixes like `0.5C`
- Improved numeric parsing for reported temperature values with unit suffixes

## 0.1.4

- Fixed setup failure when AWS IoT websocket handshake fails
- Added graceful fallback to REST-only polling mode

## 0.1.3

- Added `install.sh` for shell-based manual installation
- Expanded README/README-ko with badges and installation methods (HACS/manual/shell)
- Added Home Assistant shortcut badges for repository and config flow

## 0.1.2

- Fixed HACS `hacs.json` schema (`domains` removed)
- Adjusted HACS Validate workflow to ignore `brands` check until brand submission
- Kept Hassfest requirements satisfied (`manifest` ordering and `CONFIG_SCHEMA`)

## 0.1.1

- Switched repository focus to Home Assistant custom integration
- Added HACS include requirements (issues, topics, release workflow alignment)
- Added/updated HACS validation and hassfest workflows
- Updated manifest metadata for current repository

## 0.1.0

- Converted repository to Home Assistant custom integration focus
- Added `custom_components/navien_smart`
- Added HACS metadata (`hacs.json`)
- Added validation workflows (`hacs/action`, `hassfest`)
- Removed legacy Homebridge/TypeScript implementation from this repository
