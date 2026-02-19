"""The Navien Smart integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCOUNT_SEQ,
    CONF_AUTH_MODE,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_SEPARATE_CONTROL,
    CONF_SOUND_ENABLED,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SEPARATE_CONTROL,
    DEFAULT_SOUND_ENABLED,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import NavienDataCoordinator
from .navien_api import NavienApiClient


NavienEntryData = dict[str, Any]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Navien Smart integration."""

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Navien Smart from a config entry."""

    session = async_get_clientsession(hass)

    sound_enabled = entry.options.get(
        CONF_SOUND_ENABLED,
        entry.data.get(CONF_SOUND_ENABLED, DEFAULT_SOUND_ENABLED),
    )
    scan_interval = int(
        entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
    )

    client = NavienApiClient(
        session=session,
        auth_mode=entry.data[CONF_AUTH_MODE],
        username=entry.data[CONF_USERNAME],
        password=entry.data.get(CONF_PASSWORD),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        account_seq=entry.data.get(CONF_ACCOUNT_SEQ),
        sound_enabled=bool(sound_enabled),
    )

    coordinator = NavienDataCoordinator(
        hass=hass,
        client=client,
        scan_interval=scan_interval,
    )
    await coordinator.async_config_entry_first_refresh()

    entry_data: NavienEntryData = {
        "client": client,
        "coordinator": coordinator,
        CONF_SEPARATE_CONTROL: bool(
            entry.options.get(
                CONF_SEPARATE_CONTROL,
                entry.data.get(CONF_SEPARATE_CONTROL, DEFAULT_SEPARATE_CONTROL),
            )
        ),
    }

    hass.data[DOMAIN][entry.entry_id] = entry_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    data = hass.data[DOMAIN].pop(entry.entry_id)
    client: NavienApiClient = data["client"]
    await client.async_shutdown()

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""

    await hass.config_entries.async_reload(entry.entry_id)
