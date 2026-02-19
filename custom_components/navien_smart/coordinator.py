"""Data coordinator for Navien Smart."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .models import (
    NavienDevice,
    NavienDeviceStatus,
    adjust_parsed_status,
    merge_status,
    parse_reported_state,
)
from .navien_api import NavienApiClient, NavienApiError, extract_status_payload

_LOGGER = logging.getLogger(__name__)


class NavienDataCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinate device list and status updates for Navien Smart."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NavienApiClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Navien Smart",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self._devices: dict[str, NavienDevice] = {}
        self._statuses: dict[str, NavienDeviceStatus] = {}

    @property
    def devices(self) -> dict[str, NavienDevice]:
        return self._devices

    @property
    def statuses(self) -> dict[str, NavienDeviceStatus]:
        return self._statuses

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            await self.client.async_prepare()
            await self.client.async_start_status_stream(self.hass.loop, self.async_process_status_event)

            devices = await self.client.async_get_devices()
            self._devices = {device.device_id: device for device in devices}

            stale_ids = [device_id for device_id in self._statuses if device_id not in self._devices]
            for device_id in stale_ids:
                self._statuses.pop(device_id, None)

            for device in devices:
                self._statuses.setdefault(device.device_id, NavienDeviceStatus.initial(device))

            requests = [self.client.async_request_status(device) for device in devices]
            if requests:
                results = await asyncio.gather(*requests, return_exceptions=True)
                for device, result in zip(devices, results, strict=True):
                    if isinstance(result, Exception):
                        _LOGGER.debug(
                            "Status refresh request failed for %s (%s): %s",
                            device.name,
                            device.device_id,
                            result,
                        )

            return self._snapshot()
        except NavienApiError as err:
            raise UpdateFailed(err) from err

    def async_process_status_event(self, event: dict[str, Any]) -> None:
        """Handle incoming MQTT status event."""

        device_id, reported = extract_status_payload(event)
        if not device_id or reported is None:
            return

        device = self._devices.get(device_id)
        if device is None:
            return

        current = self._statuses.get(device_id)
        if current is None:
            current = NavienDeviceStatus.initial(device)

        parsed = parse_reported_state(reported, device.is_double)
        adjusted = adjust_parsed_status(
            parsed,
            current.left_target_temperature,
            current.right_target_temperature,
            device.heat_range,
        )
        updated = merge_status(current, adjusted)

        if updated == current:
            return

        self._statuses[device_id] = updated
        self.async_set_updated_data(self._snapshot())

    def async_apply_operation_mode(self, device_id: str, is_on: bool) -> None:
        """Optimistically apply power mode."""

        status = self._statuses.get(device_id)
        if status is None:
            return

        self._statuses[device_id] = replace(status, is_power_on=is_on)
        self.async_set_updated_data(self._snapshot())

    def async_apply_target_temperature(
        self,
        device_id: str,
        temperature: float,
        zone: str | None,
    ) -> None:
        """Optimistically apply target temperature."""

        status = self._statuses.get(device_id)
        device = self._devices.get(device_id)
        if status is None or device is None:
            return

        if zone in (None, "single"):
            left_enabled = temperature > device.heat_range.minimum
            if device.is_double and zone is None:
                self._statuses[device_id] = replace(
                    status,
                    left_target_temperature=temperature,
                    right_target_temperature=temperature,
                    left_enabled=left_enabled,
                    right_enabled=left_enabled,
                )
            else:
                self._statuses[device_id] = replace(
                    status,
                    left_target_temperature=temperature,
                    left_enabled=left_enabled,
                )
        elif zone == "left":
            self._statuses[device_id] = replace(
                status,
                left_target_temperature=temperature,
                left_enabled=temperature > device.heat_range.minimum,
            )
        elif zone == "right":
            self._statuses[device_id] = replace(
                status,
                right_target_temperature=temperature,
                right_enabled=temperature > device.heat_range.minimum,
            )

        self.async_set_updated_data(self._snapshot())

    def _snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            "devices": dict(self._devices),
            "statuses": dict(self._statuses),
        }
