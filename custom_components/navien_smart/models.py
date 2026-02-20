"""Data models for Navien Smart."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Literal

HeatingZone = Literal["single", "left", "right"]


@dataclass(slots=True, frozen=True)
class HeatRange:
    """Temperature control range."""

    minimum: float
    maximum: float
    step: float


@dataclass(slots=True, frozen=True)
class NavienDevice:
    """Navien device metadata."""

    device_seq: int
    service_code: int
    device_id: str
    model_code: str
    model_name: str
    name: str
    left_name: str | None
    right_name: str | None
    heat_range: HeatRange
    connected: bool

    @property
    def is_double(self) -> bool:
        return self.left_name is not None and self.right_name is not None

    @classmethod
    def from_api_data(cls, raw: dict[str, Any]) -> "NavienDevice":
        props = raw["Properties"]
        nickname = props["nickName"]
        side = nickname.get("side") or {}

        heat_control = props["registry"]["attributes"]["functions"]["heatControl"]
        step = _to_float(heat_control.get("unit"))
        minimum_raw = _to_float(heat_control.get("rangeMin"))
        maximum = _to_float(heat_control.get("rangeMax"))
        if step is None or minimum_raw is None or maximum is None:
            raise ValueError(f"Invalid heatControl values: {heat_control!r}")
        minimum = minimum_raw - step

        return cls(
            device_seq=int(raw["deviceSeq"]),
            service_code=int(raw["serviceCode"]),
            device_id=str(raw["deviceId"]),
            model_code=str(raw["modelCode"]),
            model_name=str(raw.get("modelName", "Navien")),
            name=str(nickname["mainItem"]),
            left_name=side.get("left"),
            right_name=side.get("right"),
            heat_range=HeatRange(minimum=minimum, maximum=maximum, step=step),
            connected=bool(raw.get("connected", 0)),
        )


@dataclass(slots=True, frozen=True)
class AwsCredentials:
    """Temporary AWS credentials used for MQTT status subscription."""

    access_key_id: str
    secret_access_key: str
    session_token: str
    expires_at: float


@dataclass(slots=True, frozen=True)
class NavienDeviceStatus:
    """Runtime device status parsed from AWS shadow update events."""

    is_connected: bool
    is_power_on: bool
    left_enabled: bool
    right_enabled: bool
    left_current_temperature: float | None
    right_current_temperature: float | None
    left_target_temperature: float
    right_target_temperature: float
    is_locked: bool

    @classmethod
    def initial(cls, device: NavienDevice) -> "NavienDeviceStatus":
        return cls(
            is_connected=device.connected,
            is_power_on=False,
            left_enabled=False,
            right_enabled=False,
            left_current_temperature=None,
            right_current_temperature=None,
            left_target_temperature=device.heat_range.minimum,
            right_target_temperature=device.heat_range.minimum,
            is_locked=False,
        )

    def zone_enabled(self, zone: HeatingZone | None) -> bool:
        if zone in (None, "single", "left"):
            return self.left_enabled
        return self.right_enabled

    def zone_idle(self, zone: HeatingZone | None) -> bool:
        if not self.is_power_on:
            return False

        if zone in (None, "single", "left"):
            current = self.current_temperature(zone)
            target = self.target_temperature(zone)
            return target <= current

        current = self.current_temperature("right")
        target = self.target_temperature("right")
        return target <= current

    def current_temperature(self, zone: HeatingZone | None) -> float:
        if zone in (None, "single", "left"):
            return self.left_current_temperature or self.left_target_temperature
        return self.right_current_temperature or self.right_target_temperature

    def target_temperature(self, zone: HeatingZone | None) -> float:
        if zone in (None, "single", "left"):
            return self.left_target_temperature
        return self.right_target_temperature


@dataclass(slots=True, frozen=True)
class ParsedStatus:
    """Intermediate parsed status from a shadow document."""

    is_connected: bool
    is_power_on: bool | None = None
    left_enabled: bool | None = None
    right_enabled: bool | None = None
    left_current_temperature: float | None = None
    right_current_temperature: float | None = None
    left_target_temperature: float | None = None
    right_target_temperature: float | None = None
    is_locked: bool | None = None


def parse_reported_state(reported: dict[str, Any], is_double: bool) -> ParsedStatus:
    """Parse AWS shadow `reported` state to a normalized partial status."""

    is_connected = bool(reported.get("connected", False))
    parsed = ParsedStatus(is_connected=is_connected)

    if not is_connected:
        return parsed

    operation_mode = reported.get("operationMode")
    is_power_on = None if operation_mode is None else int(operation_mode) == 1

    left_enabled: bool | None = None
    right_enabled: bool | None = None
    left_current: float | None = None
    right_current: float | None = None
    left_target: float | None = None
    right_target: float | None = None

    heater = reported.get("heater")
    if isinstance(heater, dict):
        if is_double:
            left = heater.get("left") if isinstance(heater.get("left"), dict) else {}
            right = heater.get("right") if isinstance(heater.get("right"), dict) else {}

            left_enabled = left.get("enable")
            right_enabled = right.get("enable")

            left_temp = left.get("temperature") if isinstance(left.get("temperature"), dict) else {}
            right_temp = right.get("temperature") if isinstance(right.get("temperature"), dict) else {}

            left_current = left_temp.get("current")
            left_target = left_temp.get("set")
            right_current = right_temp.get("current")
            right_target = right_temp.get("set")
        else:
            single = heater.get("single") if isinstance(heater.get("single"), dict) else {}
            single_temp = single.get("temperature") if isinstance(single.get("temperature"), dict) else {}

            left_enabled = single.get("enable")
            left_current = single_temp.get("current")
            left_target = single_temp.get("set")

    return ParsedStatus(
        is_connected=is_connected,
        is_power_on=is_power_on,
        left_enabled=left_enabled,
        right_enabled=right_enabled,
        left_current_temperature=_to_float(left_current),
        right_current_temperature=_to_float(right_current),
        left_target_temperature=_to_float(left_target),
        right_target_temperature=_to_float(right_target),
        is_locked=_to_bool(reported.get("childLock")),
    )


def adjust_parsed_status(
    parsed: ParsedStatus,
    left_target_temperature: float,
    right_target_temperature: float,
    heat_range: HeatRange,
) -> ParsedStatus:
    """Mirror the Homebridge status adjustment logic."""

    adjusted_left_target = parsed.left_target_temperature
    adjusted_left_enabled = parsed.left_enabled
    adjusted_right_target = parsed.right_target_temperature
    adjusted_right_enabled = parsed.right_enabled

    if adjusted_left_enabled is not None:
        if adjusted_left_enabled and left_target_temperature <= heat_range.minimum:
            adjusted_left_target = heat_range.minimum + heat_range.step
        if not adjusted_left_enabled and left_target_temperature > heat_range.minimum:
            adjusted_left_target = heat_range.minimum

    if adjusted_left_target is not None:
        adjusted_left_enabled = adjusted_left_target > heat_range.minimum

    if adjusted_right_enabled is not None:
        if adjusted_right_enabled and right_target_temperature <= heat_range.minimum:
            adjusted_right_target = heat_range.minimum + heat_range.step
        if not adjusted_right_enabled and right_target_temperature > heat_range.minimum:
            adjusted_right_target = heat_range.minimum

    if adjusted_right_target is not None:
        adjusted_right_enabled = adjusted_right_target > heat_range.minimum

    return replace(
        parsed,
        left_target_temperature=adjusted_left_target,
        left_enabled=adjusted_left_enabled,
        right_target_temperature=adjusted_right_target,
        right_enabled=adjusted_right_enabled,
    )


def merge_status(
    current: NavienDeviceStatus,
    parsed: ParsedStatus,
) -> NavienDeviceStatus:
    """Apply parsed partial status to current immutable status."""

    return NavienDeviceStatus(
        is_connected=parsed.is_connected,
        is_power_on=current.is_power_on if parsed.is_power_on is None else parsed.is_power_on,
        left_enabled=current.left_enabled if parsed.left_enabled is None else parsed.left_enabled,
        right_enabled=current.right_enabled if parsed.right_enabled is None else parsed.right_enabled,
        left_current_temperature=(
            current.left_current_temperature
            if parsed.left_current_temperature is None
            else parsed.left_current_temperature
        ),
        right_current_temperature=(
            current.right_current_temperature
            if parsed.right_current_temperature is None
            else parsed.right_current_temperature
        ),
        left_target_temperature=(
            current.left_target_temperature
            if parsed.left_target_temperature is None
            else parsed.left_target_temperature
        ),
        right_target_temperature=(
            current.right_target_temperature
            if parsed.right_target_temperature is None
            else parsed.right_target_temperature
        ),
        is_locked=current.is_locked if parsed.is_locked is None else parsed.is_locked,
    )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            match = re.search(r"[-+]?\d+(?:\.\d+)?", value.strip())
            if not match:
                return None
            try:
                return float(match.group(0))
            except ValueError:
                return None

    return None


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return None
