# Home Assistant용 Navien Smart

나비엔 스마트 온수매트를 제어하기 위한 Home Assistant 커스텀 통합입니다.

## 기능

- 설정 플로우 지원 (`설정` -> `기기 및 서비스` -> `통합 추가`)
- 인증 방식
  - `account`: 아이디 + 비밀번호
  - `token`: 아이디 + refresh token + account sequence
- 온수매트 `climate` 엔티티 제공
- 2구 기기 좌/우 분리 모드(`separate_control`) 지원
- AWS IoT MQTT 기반 실시간 상태 반영

## 설치 (HACS)

1. HACS를 엽니다.
2. `통합` -> 우측 상단 메뉴 -> `커스텀 저장소`로 이동합니다.
3. 이 저장소 URL을 추가하고 카테고리를 `Integration`으로 선택합니다.
4. `Navien Smart`를 검색해 설치합니다.
5. Home Assistant를 재시작합니다.
6. `설정` -> `기기 및 서비스` -> `통합 추가` -> `Navien Smart`를 선택합니다.

## 통합 옵션

- `auth_mode`: `account` 또는 `token`
- `separate_control`: 2구 기기의 좌/우 엔티티를 분리
- `sound_enabled`: 지원 기기에서 조작 알림음 사용
- `scan_interval`: 코디네이터 폴링 주기(초)

## 참고

- 이 통합은 비공식 API(리버스 엔지니어링 기반)를 사용합니다.
- 지원 모델은 제한적이며, 기기/펌웨어에 따라 동작 차이가 있을 수 있습니다.
- 이 저장소의 기존 Homebridge 구현은 제거되었고, 현재는 Python/HA 전용 저장소입니다.

## 개발

통합 소스 경로:

- `custom_components/navien_smart`

검증 워크플로우:

- `.github/workflows/validate.yml`
- `.github/workflows/hassfest.yml`
