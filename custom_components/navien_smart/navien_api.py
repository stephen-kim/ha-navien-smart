"""Navien Smart API client and MQTT status subscriber."""

from __future__ import annotations

import json
import logging
import re
import ssl
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import aiohttp
import paho.mqtt.client as mqtt
from botocore.auth import SigV4QueryAuth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from .const import (
    API_URL,
    AUTH_MODE_ACCOUNT,
    AWS_IOT_ENDPOINT,
    AWS_IOT_REGION,
    LOGIN_API_URL,
    OPERATION_MODE_OFF,
    OPERATION_MODE_ON,
    RESPONSE_SUCCESS,
    RESPONSE_TOKEN_EXPIRED,
    USER_AGENT,
)
from .models import AwsCredentials, HeatingZone, NavienDevice

_LOGGER = logging.getLogger(__name__)


class NavienApiError(Exception):
    """Base Navien API error."""


class NavienAuthError(NavienApiError):
    """Authentication error."""


class NavienMqttClient:
    """AWS IoT MQTT-over-websocket client for Navien status events."""

    def __init__(
        self,
        loop,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        self._loop = loop
        self._callback = callback
        self._client: mqtt.Client | None = None
        self._home_seq: int | None = None
        self._signature: tuple[int, int, str] | None = None

    async def async_ensure_started(
        self,
        home_seq: int,
        user_seq: int,
        credentials: AwsCredentials,
    ) -> None:
        signature = (home_seq, user_seq, credentials.session_token)

        if self._client is not None and self._signature == signature and self._client.is_connected():
            return

        await self.async_stop()

        self._home_seq = home_seq
        self._signature = signature

        ws_url = _build_signed_mqtt_url(credentials)
        split = urlsplit(ws_url)
        path = split.path + (f"?{split.query}" if split.query else "")

        client = mqtt.Client(
            client_id=f"{uuid4()}-U{user_seq}",
            transport="websockets",
            protocol=mqtt.MQTTv311,
        )
        client.enable_logger(_LOGGER)
        client.reconnect_delay_set(min_delay=1, max_delay=120)
        # Keep Host header aligned with signed URL host to avoid SigV4 mismatch.
        ws_headers = {"Host": split.netloc or (split.hostname or AWS_IOT_ENDPOINT)}
        client.ws_set_options(path=path, headers=ws_headers)
        client.tls_set_context(ssl.create_default_context())

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect

        def _start() -> None:
            client.connect(split.hostname or AWS_IOT_ENDPOINT, split.port or 443, keepalive=60)
            client.loop_start()

        await self._loop.run_in_executor(None, _start)
        self._client = client

    async def async_stop(self) -> None:
        if self._client is None:
            return

        client = self._client
        self._client = None

        def _stop() -> None:
            try:
                client.disconnect()
            finally:
                client.loop_stop()

        await self._loop.run_in_executor(None, _stop)

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, rc: int, _properties: Any = None) -> None:
        if rc != 0:
            _LOGGER.warning("Navien MQTT connect failed: rc=%s", rc)
            return

        if self._home_seq is None:
            return

        topic = f"{self._home_seq}/mate/+"
        client.subscribe(topic)
        _LOGGER.debug("Navien MQTT subscribed topic: %s", topic)

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, rc: int, _properties: Any = None) -> None:
        if rc != 0:
            _LOGGER.warning("Navien MQTT disconnected unexpectedly: rc=%s", rc)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return

        if not isinstance(payload, dict):
            return

        if not _is_status_event(payload):
            return

        self._loop.call_soon_threadsafe(self._callback, payload)


class NavienApiClient:
    """Navien REST + AWS status stream client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth_mode: str,
        username: str,
        password: str | None,
        refresh_token: str | None,
        account_seq: int | None,
        sound_enabled: bool,
    ) -> None:
        self._session = session
        self._auth_mode = auth_mode
        self._username = username
        self._password = password
        self._refresh_token = refresh_token
        self._account_seq = account_seq
        self._sound_enabled = sound_enabled

        self._access_token: str | None = None
        self._access_token_expires_at: float = 0

        self._user_id: str | None = None
        self._user_seq: int | None = None
        self._home_seq: int | None = None
        self._aws_credentials: AwsCredentials | None = None

        self._mqtt: NavienMqttClient | None = None

    @property
    def account_seq(self) -> int | None:
        return self._account_seq

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @property
    def user_id(self) -> str:
        return self._user_id or self._username

    async def async_prepare(self) -> None:
        """Ensure API and AWS sessions are ready."""

        if self._auth_mode == AUTH_MODE_ACCOUNT and not self._refresh_token:
            await self._async_login_with_account()

        if not self._refresh_token:
            raise NavienAuthError("Missing refresh token")

        if self._account_seq is None:
            raise NavienAuthError("Missing account sequence")

        if not self._access_token or self._is_access_token_expired():
            try:
                await self._async_refresh_access_token()
            except NavienAuthError:
                if self._auth_mode != AUTH_MODE_ACCOUNT:
                    raise
                await self._async_login_with_account()
                await self._async_refresh_access_token()

        if self._should_refresh_aws_session():
            await self._async_token_login()

    async def async_start_status_stream(self, hass_loop, callback: Callable[[dict[str, Any]], None]) -> None:
        """Start (or refresh) MQTT status stream."""

        if self._home_seq is None or self._user_seq is None or self._aws_credentials is None:
            raise NavienApiError("Client not prepared")

        if self._mqtt is None:
            self._mqtt = NavienMqttClient(hass_loop, callback)

        try:
            await self._mqtt.async_ensure_started(self._home_seq, self._user_seq, self._aws_credentials)
            return
        except Exception as first_err:  # noqa: BLE001
            _LOGGER.debug(
                "Navien MQTT initial start failed; refreshing AWS session and retrying once: %s",
                first_err,
            )

        # Retry once with a fresh AWS session since temporary credentials can become invalid.
        await self._async_token_login()
        if self._home_seq is None or self._user_seq is None or self._aws_credentials is None:
            raise NavienApiError("Client not prepared after AWS session refresh")
        await self._mqtt.async_ensure_started(self._home_seq, self._user_seq, self._aws_credentials)

    async def async_shutdown(self) -> None:
        """Shutdown MQTT client."""

        if self._mqtt is not None:
            await self._mqtt.async_stop()

    async def async_get_devices(self) -> list[NavienDevice]:
        """Get all devices for the current home."""

        if self._home_seq is None or self._user_seq is None:
            raise NavienApiError("Client not prepared")

        payload = await self._async_request(
            "GET",
            "/devices",
            query={"homeSeq": str(self._home_seq), "userSeq": str(self._user_seq)},
        )

        devices = payload.get("data", {}).get("devices", [])
        if not isinstance(devices, list):
            raise NavienApiError("Invalid devices response")

        return [NavienDevice.from_api_data(item) for item in devices if isinstance(item, dict)]

    async def async_request_status(self, device: NavienDevice) -> None:
        """Request shadow status refresh for a device."""

        await self._async_control_device(device)

    async def async_set_operation_mode(self, device: NavienDevice, is_on: bool) -> None:
        """Set device operation mode."""

        await self._async_control_device(
            device,
            payload={"operationMode": OPERATION_MODE_ON if is_on else OPERATION_MODE_OFF},
        )

    async def async_set_temperature(
        self,
        device: NavienDevice,
        temperature: float,
        zone: HeatingZone | None,
    ) -> None:
        """Set target temperature for a zone or unified control."""

        _validate_temperature(device, temperature)
        enabled = temperature > device.heat_range.minimum

        if zone is None:
            if device.is_double:
                payload = {
                    "operationMode": OPERATION_MODE_ON if enabled else None,
                    "heater": {
                        "left": {"enable": enabled, "temperature": {"set": temperature}},
                        "right": {"enable": enabled, "temperature": {"set": temperature}},
                    },
                }
            else:
                payload = {
                    "operationMode": OPERATION_MODE_ON if enabled else None,
                    "heater": {
                        "single": {"enable": enabled, "temperature": {"set": temperature}},
                    },
                }
        else:
            if zone == "single" and device.is_double:
                raise NavienApiError('Zone "single" is not valid for double devices')
            if zone in ("left", "right") and not device.is_double:
                raise NavienApiError(f'Zone "{zone}" is not valid for single devices')

            payload = {
                "operationMode": OPERATION_MODE_ON if enabled else None,
                "heater": {
                    zone: {"enable": enabled, "temperature": {"set": temperature}},
                },
            }

        await self._async_control_device(device, payload)

    async def async_set_child_lock(self, device: NavienDevice, is_locked: bool) -> None:
        """Set child lock state."""

        await self._async_control_device(device, payload={"childLock": is_locked})

    async def _async_control_device(self, device: NavienDevice, payload: dict[str, Any] | None = None) -> None:
        if self._home_seq is None or self._user_seq is None:
            raise NavienApiError("Client not prepared")

        model_code = int(device.model_code)
        desired: dict[str, Any] = {
            "event": {"modelCode": model_code},
            "beep": payload is not None and self._sound_enabled,
        }

        if payload:
            desired.update(payload)

        body = {
            "serviceCode": device.service_code,
            "topic": f"$aws/things/{device.device_id}/shadow/name/status/update",
            "payload": {
                "state": {
                    "desired": desired,
                }
            },
        }

        response = await self._async_request(
            "POST",
            f"/devices/{device.device_seq}/control",
            query={"homeSeq": str(self._home_seq), "userSeq": str(self._user_seq)},
            json_data=body,
        )

        if int(response.get("code", 0)) != RESPONSE_SUCCESS:
            raise NavienApiError(response.get("msg", "Failed to control device"))

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        retry: bool = True,
    ) -> dict[str, Any]:
        if not self._access_token and path not in ("/auth/token/refresh",):
            await self.async_prepare()

        url = f"{API_URL}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"

        headers: dict[str, str] = {}
        if self._access_token:
            headers["Authorization"] = self._access_token
        if json_data is not None:
            headers["Content-Type"] = "application/json"

        async with self._session.request(method, url, headers=headers, json=json_data) as response:
            payload = await _read_json(response)

        code = int(payload.get("code", 0)) if isinstance(payload.get("code"), (int, float)) else None

        if code == RESPONSE_TOKEN_EXPIRED and retry:
            await self._async_refresh_access_token()
            return await self._async_request(
                method,
                path,
                query=query,
                json_data=json_data,
                retry=False,
            )

        if response.status >= 400:
            raise NavienApiError(payload.get("msg", f"HTTP {response.status}"))

        return payload

    async def _async_refresh_access_token(self) -> None:
        if not self._refresh_token:
            raise NavienAuthError("Missing refresh token")

        async with self._session.post(
            f"{API_URL}/auth/token/refresh",
            headers={"Content-Type": "application/json"},
            json={"refreshToken": self._refresh_token},
        ) as response:
            payload = await _read_json(response)

        data = payload.get("data") if isinstance(payload, dict) else None
        auth_info = data.get("authInfo") if isinstance(data, dict) else None

        if not isinstance(auth_info, dict):
            raise NavienAuthError("Refresh token expired or invalid")

        access_token = auth_info.get("accessToken")
        expires_in = auth_info.get("authenticationExpiresIn")

        if not isinstance(access_token, str) or not isinstance(expires_in, (int, float)):
            raise NavienAuthError("Invalid token refresh response")

        self._access_token = access_token
        self._access_token_expires_at = time.time() + float(expires_in)

    async def _async_token_login(self) -> None:
        if not self._access_token:
            raise NavienAuthError("Missing access token")
        if self._account_seq is None:
            raise NavienAuthError("Missing account sequence")

        user_id = self._user_id or self._username

        async with self._session.post(
            f"{API_URL}/users/secured-sign-in",
            headers={
                "Authorization": self._access_token,
                "Content-Type": "application/json",
            },
            json={"userId": user_id, "accountSeq": self._account_seq},
        ) as response:
            payload = await _read_json(response)

        if response.status == 401:
            raise NavienAuthError("Access token expired")

        if int(payload.get("code", 0)) != RESPONSE_SUCCESS:
            raise NavienApiError(payload.get("msg", "Token login failed"))

        data = payload.get("data")
        if not isinstance(data, dict):
            raise NavienApiError("Invalid token login response")

        user_info = data.get("userInfo") if isinstance(data.get("userInfo"), dict) else None
        homes = data.get("home") if isinstance(data.get("home"), list) else []
        auth_info = data.get("authInfo") if isinstance(data.get("authInfo"), dict) else None

        if not user_info or not homes or not isinstance(homes[0], dict) or not auth_info:
            raise NavienApiError("Missing fields in token login response")

        self._user_id = str(user_info.get("userId", user_id))
        self._user_seq = int(user_info["userSeq"])
        self._home_seq = int(homes[0]["homeSeq"])

        self._aws_credentials = AwsCredentials(
            access_key_id=str(auth_info["accessKeyId"]),
            secret_access_key=str(auth_info["secretKey"]),
            session_token=str(auth_info["sessionToken"]),
            expires_at=time.time() + float(auth_info["authorizationExpiresIn"]),
        )

    async def _async_login_with_account(self) -> None:
        if not self._password:
            raise NavienAuthError("Password is required for account auth mode")

        async with self._session.post(
            f"{LOGIN_API_URL}/member/login",
            headers={
                "User-Agent": USER_AGENT,
                "Origin": LOGIN_API_URL,
                "Referer": f"{LOGIN_API_URL}/member/login",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"username": self._username, "password": self._password},
            allow_redirects=True,
        ) as response:
            html = await response.text()

        if not _is_login_success(html):
            raise NavienAuthError(_get_login_error_message(html))

        if "passwordChg" in html:
            await self._async_password_change_later()
            async with self._session.post(
                f"{LOGIN_API_URL}/member/login",
                headers={
                    "User-Agent": USER_AGENT,
                    "Origin": LOGIN_API_URL,
                    "Referer": f"{LOGIN_API_URL}/member/login",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"username": self._username, "password": self._password},
                allow_redirects=True,
            ) as retry_response:
                html = await retry_response.text()

            if not _is_login_success(html):
                raise NavienAuthError(_get_login_error_message(html))

        json_string = _extract_login_json(html)
        if not json_string:
            raise NavienAuthError("Failed to parse login response")

        payload = json.loads(json_string)
        self._refresh_token = str(payload["refreshToken"])
        self._account_seq = int(payload["userSeq"])
        self._user_id = str(payload["loginId"])

    async def _async_password_change_later(self) -> None:
        async with self._session.post(
            f"{LOGIN_API_URL}/pwchgLate",
            headers={"Content-Type": "application/json"},
        ):
            return

    def _is_access_token_expired(self) -> bool:
        return self._access_token_expires_at <= time.time() + 10

    def _should_refresh_aws_session(self) -> bool:
        if self._user_seq is None or self._home_seq is None or self._aws_credentials is None:
            return True
        return self._aws_credentials.expires_at <= time.time() + 60


def _validate_temperature(device: NavienDevice, temperature: float) -> None:
    minimum = device.heat_range.minimum
    maximum = device.heat_range.maximum
    step = device.heat_range.step

    if temperature < minimum or temperature > maximum:
        raise NavienApiError(
            f"Temperature must be between {minimum} and {maximum}. current={temperature}"
        )

    units = (temperature - minimum) / step
    if abs(units - round(units)) > 1e-6:
        raise NavienApiError(f"Temperature must follow step {step}. current={temperature}")


def extract_status_payload(event: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    """Extract (device_id, reported_state) from Navien MQTT event payload."""

    topic = event.get("topic")
    if not isinstance(topic, str):
        return None, None

    match = re.match(r"^\$aws/things/(?P<device_id>[^/]+)/shadow/name/status/update/accepted$", topic)
    if not match:
        return None, None

    payload = event.get("payload")
    if not isinstance(payload, dict):
        return match.group("device_id"), None

    state = payload.get("state")
    if not isinstance(state, dict):
        return match.group("device_id"), None

    reported = state.get("reported")
    if not isinstance(reported, dict):
        return match.group("device_id"), None

    return match.group("device_id"), reported


def _build_signed_mqtt_url(credentials: AwsCredentials) -> str:
    request = AWSRequest(method="GET", url=f"wss://{AWS_IOT_ENDPOINT}/mqtt")
    sigv4 = SigV4QueryAuth(
        Credentials(
            access_key=credentials.access_key_id,
            secret_key=credentials.secret_access_key,
            token=credentials.session_token,
        ),
        "iotdevicegateway",
        AWS_IOT_REGION,
        expires=900,
    )
    sigv4.add_auth(request)
    return request.url


def _is_status_event(payload: dict[str, Any]) -> bool:
    topic = payload.get("topic")
    if not isinstance(topic, str):
        return False
    if not topic.endswith("/shadow/name/status/update/accepted"):
        return False

    body = payload.get("payload")
    if not isinstance(body, dict):
        return False
    state = body.get("state")
    if not isinstance(state, dict):
        return False
    reported = state.get("reported")
    return isinstance(reported, dict)


async def _read_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
    try:
        payload = await response.json(content_type=None)
    except (aiohttp.ContentTypeError, json.JSONDecodeError):
        text = await response.text()
        raise NavienApiError(f"Invalid response: {text[:200]}")

    if not isinstance(payload, dict):
        raise NavienApiError("Unexpected response format")
    return payload


def _is_login_success(html: str) -> bool:
    return 'id="loginFailPopup" style="display:none;"' not in html


def _get_login_error_message(html: str) -> str:
    if "입력한 정보가 일치하지 않습니다." not in html:
        return "Username is incorrect"

    match = re.search(r"현재\s+(\d)회", html)
    if match:
        count = match.group(1)
        return (
            "Password is incorrect. If you fail 5 times, "
            f"password reset may be required. (current={count})"
        )

    return "Password is incorrect. Password reset may be required"


def _extract_login_json(html: str) -> str | None:
    lines = [line.strip() for line in html.splitlines() if "var message = " in line]
    if not lines:
        return None

    line = lines[0]
    start = line.find("{")
    end = line.rfind("}")
    if start < 0 or end < 0:
        return None

    return line[start : end + 1]
