"""Constants for the Navien Smart integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "navien_smart"
PLATFORMS: list[Platform] = [Platform.CLIMATE]

CONF_AUTH_MODE = "auth_mode"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCOUNT_SEQ = "account_seq"
CONF_SEPARATE_CONTROL = "separate_control"
CONF_SOUND_ENABLED = "sound_enabled"
CONF_SCAN_INTERVAL = "scan_interval"

AUTH_MODE_ACCOUNT = "account"
AUTH_MODE_TOKEN = "token"

DEFAULT_SEPARATE_CONTROL = False
DEFAULT_SOUND_ENABLED = False
DEFAULT_SCAN_INTERVAL = 120
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 600

API_URL = "https://nskr.naviensmartcontrol.com/api/v2.0"
LOGIN_API_URL = "https://member.naviensmartcontrol.com"

AWS_IOT_REGION = "ap-northeast-2"
AWS_IOT_ENDPOINT = f"a1o5esupplsltq-ats.iot.{AWS_IOT_REGION}.amazonaws.com"

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 APP_NAVIENSMART_IOS"
)

OPERATION_MODE_OFF = 0
OPERATION_MODE_ON = 1

RESPONSE_SUCCESS = 200
RESPONSE_NOT_AUTHORIZED = 404
RESPONSE_TOKEN_EXPIRED = 407
