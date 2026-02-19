"""Climate platform for Navien Smart."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SEPARATE_CONTROL, DOMAIN
from .coordinator import NavienDataCoordinator
from .models import HeatingZone, NavienDevice
from .navien_api import NavienApiError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navien climate entities."""

    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: NavienDataCoordinator = entry_data["coordinator"]
    separate_control: bool = entry_data[CONF_SEPARATE_CONTROL]

    entities: list[NavienClimateEntity] = []
    for device in coordinator.devices.values():
        if device.is_double and separate_control:
            entities.append(NavienClimateEntity(coordinator, device, "left"))
            entities.append(NavienClimateEntity(coordinator, device, "right"))
        else:
            entities.append(NavienClimateEntity(coordinator, device, None))

    async_add_entities(entities)


class NavienClimateEntity(CoordinatorEntity[NavienDataCoordinator], ClimateEntity):
    """Navien heating mat as Home Assistant climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NavienDataCoordinator,
        device: NavienDevice,
        zone: HeatingZone | None,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device.device_id
        self._zone = zone

        if zone == "left":
            self._attr_name = device.left_name or f"{device.name} Left"
            self._attr_unique_id = f"{device.device_id}_left"
        elif zone == "right":
            self._attr_name = device.right_name or f"{device.name} Right"
            self._attr_unique_id = f"{device.device_id}_right"
        else:
            self._attr_name = device.name
            self._attr_unique_id = device.device_id

    @property
    def device_info(self):
        device = self._device
        return {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": "Navien",
            "model": device.model_name,
        }

    @property
    def min_temp(self) -> float:
        return self._device.heat_range.minimum

    @property
    def max_temp(self) -> float:
        return self._device.heat_range.maximum

    @property
    def target_temperature_step(self) -> float:
        return self._device.heat_range.step

    @property
    def available(self) -> bool:
        status = self._status
        return status.is_connected if status else False

    @property
    def current_temperature(self) -> float | None:
        status = self._status
        if status is None:
            return None
        return status.current_temperature(self._zone)

    @property
    def target_temperature(self) -> float | None:
        status = self._status
        if status is None:
            return None
        return status.target_temperature(self._zone)

    @property
    def hvac_mode(self) -> HVACMode | None:
        status = self._status
        if status is None:
            return None

        if self._zone is None:
            return HVACMode.HEAT if status.is_power_on else HVACMode.OFF

        running = status.is_power_on and status.zone_enabled(self._zone)
        return HVACMode.HEAT if running else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        status = self._status
        if status is None:
            return None

        mode = self.hvac_mode
        if mode != HVACMode.HEAT:
            return HVACAction.OFF

        if status.zone_idle(self._zone):
            return HVACAction.IDLE

        return HVACAction.HEATING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "device_id": self._device_id,
            "is_double": self._device.is_double,
        }
        if self._zone is not None:
            attrs["zone"] = self._zone
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in (HVACMode.OFF, HVACMode.HEAT):
            raise ValueError(f"Unsupported hvac mode: {hvac_mode}")

        is_on = hvac_mode == HVACMode.HEAT

        try:
            if self._zone is None:
                await self.coordinator.client.async_set_operation_mode(self._device, is_on)
                self.coordinator.async_apply_operation_mode(self._device_id, is_on)
            else:
                await self._async_set_zone_running(is_on)
        except NavienApiError as err:
            _LOGGER.error("Failed to set hvac mode for %s: %s", self._attr_name, err)
            raise

        await self._async_request_status_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        target = float(temperature)

        try:
            await self.coordinator.client.async_set_temperature(self._device, target, self._zone)
            self.coordinator.async_apply_target_temperature(self._device_id, target, self._zone)
        except NavienApiError as err:
            _LOGGER.error("Failed to set target temperature for %s: %s", self._attr_name, err)
            raise

        await self._async_request_status_refresh()

    async def _async_set_zone_running(self, is_running: bool) -> None:
        status = self._status
        if status is None or self._zone is None:
            return

        is_power_on = status.is_power_on
        is_zone_enabled = status.zone_enabled(self._zone)
        other_zone = "right" if self._zone == "left" else "left"
        is_other_zone_enabled = status.zone_enabled(other_zone)

        if (is_running and not is_power_on and is_zone_enabled) or (
            (not is_running) and is_power_on and (not is_other_zone_enabled)
        ):
            await self.coordinator.client.async_set_operation_mode(self._device, is_running)
            self.coordinator.async_apply_operation_mode(self._device_id, is_running)
            return

        minimum = self._device.heat_range.minimum
        step = self._device.heat_range.step
        target = minimum + step if is_running else minimum

        await self.coordinator.client.async_set_temperature(self._device, target, self._zone)
        self.coordinator.async_apply_target_temperature(self._device_id, target, self._zone)

    async def _async_request_status_refresh(self) -> None:
        try:
            await self.coordinator.client.async_request_status(self._device)
        except NavienApiError:
            # Coordinator periodic refresh and MQTT stream will eventually recover state.
            return

    @property
    def _device(self) -> NavienDevice:
        return self.coordinator.devices[self._device_id]

    @property
    def _status(self):
        return self.coordinator.statuses.get(self._device_id)
