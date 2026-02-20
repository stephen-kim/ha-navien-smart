[![version](https://img.shields.io/github/manifest-json/v/stephen-kim/ha-navien-smart?filename=custom_components%2Fnavien_smart%2Fmanifest.json)](https://github.com/stephen-kim/ha-navien-smart/releases/latest)
[![releases](https://img.shields.io/github/downloads/stephen-kim/ha-navien-smart/total)](https://github.com/stephen-kim/ha-navien-smart/releases)
[![issues](https://img.shields.io/github/issues/stephen-kim/ha-navien-smart)](https://github.com/stephen-kim/ha-navien-smart/issues)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

# Home Assistant용 Navien Smart

나비엔 스마트 온수매트를 제어하기 위한 Home Assistant 커스텀 통합입니다.

[English](https://github.com/stephen-kim/ha-navien-smart/blob/latest/README.md) | 한국어

![demo](https://raw.githubusercontent.com/kyle-seongwoo-jun/homebridge-navien-smart/latest/docs/demo.jpg)

## 기능

- 설정 플로우 지원 (`설정` -> `기기 및 서비스` -> `통합 추가`)
- 인증 방식
  - `account`: 아이디 + 비밀번호
  - `token`: 아이디 + refresh token + account sequence
- 온수매트 `climate` 엔티티 제공
- 2구 기기 좌/우 분리 모드(`separate_control`) 지원
- AWS IoT MQTT 기반 실시간 상태 반영

## 설치

### 방법 1: HACS

1. HACS를 엽니다.
2. `통합` -> 우측 상단 메뉴 -> `커스텀 저장소`로 이동합니다.
3. 이 저장소 URL을 추가하고 카테고리를 `Integration`으로 선택합니다.
4. `Navien Smart`를 검색해 설치합니다.
5. Home Assistant를 재시작합니다.
6. `설정` -> `기기 및 서비스` -> `통합 추가` -> `Navien Smart`를 선택합니다.

바로가기:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stephen-kim&repository=ha-navien-smart)

### 방법 2: 수동 설치 (Samba / SFTP)

`custom_components/navien_smart` 폴더를 Home Assistant 설정 디렉터리의 `custom_components` 아래로 복사합니다.

### 방법 3: 쉘 설치 (SSH / Terminal)

```shell
wget -q -O - https://raw.githubusercontent.com/stephen-kim/ha-navien-smart/latest/install.sh | bash -
```

특정 버전 설치:

```shell
wget -q -O - https://raw.githubusercontent.com/stephen-kim/ha-navien-smart/latest/install.sh | ARCHIVE_TAG=v0.1.3 bash -
```

설치 후 Home Assistant를 재시작하세요.

## 통합 옵션

- `auth_mode`: `account` 또는 `token`
- `separate_control`: 2구 기기의 좌/우 엔티티를 분리
- `sound_enabled`: 지원 기기에서 조작 알림음 사용
- `scan_interval`: 코디네이터 폴링 주기(초)

### MQTT 동작

- 기본 상태 동기화는 AWS IoT MQTT(WebSocket) 실시간 업데이트를 사용합니다.
- MQTT 연결이 실패하면 통합은 자동으로 REST 폴링 모드로 전환됩니다.
- 이때 `scan_interval` 값이 상태 반영 지연 시간에 직접 영향을 줍니다.
- MQTT가 정상이어도 `scan_interval`은 세션 갱신/복구를 위한 watchdog 용도로 계속 사용됩니다.  
  실시간 연결이 안정적인 환경이면 API 호출을 줄이기 위해 `180`-`300` 정도로 높이는 것을 권장합니다.

## 참고

- 이 통합은 비공식 API(리버스 엔지니어링 기반)를 사용합니다.
- 이 플러그인은 `EME520`와 `EMW720` 모델에서만 테스트되었습니다.
- 지원 모델은 제한적이며, 기기/펌웨어에 따라 동작 차이가 있을 수 있습니다.
- 이 저장소의 기존 Homebridge 구현은 제거되었고, 현재는 Python/HA 전용 저장소입니다.

## 설정

`설정` -> `기기 및 서비스` -> `통합` -> `통합 추가` -> `Navien Smart` 검색

또는:

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=navien_smart)

### 인증 모드

- `account` (초기 설정 권장)
  - 입력값: `username`, `password`
- `token`
  - 입력값: `username`, `refresh_token`, `account_seq`
  - Home Assistant에 비밀번호를 저장하고 싶지 않을 때 사용

### 권장 옵션

- `separate_control`
  - 2구 모델에서 좌/우 climate 엔티티를 분리 생성
- `sound_enabled`
  - 지원 기기에서 동작 알림음 사용
- `scan_interval`
  - 코디네이터 상태 갱신 주기(초, 기본값 `120`)

## 개발

통합 소스 경로:

- `custom_components/navien_smart`

검증 워크플로우:

- `.github/workflows/validate.yml`
- `.github/workflows/hassfest.yml`
