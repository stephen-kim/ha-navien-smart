"""Config flow for Navien Smart."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    AUTH_MODE_ACCOUNT,
    AUTH_MODE_TOKEN,
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
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .navien_api import NavienApiClient, NavienApiError, NavienAuthError


class NavienSmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Navien Smart."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle initial setup step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            normalized = await self._async_validate_and_normalize(user_input, errors)
            if not errors:
                unique_id = f"{normalized[CONF_USERNAME]}:{normalized[CONF_ACCOUNT_SEQ]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_AUTH_MODE: normalized[CONF_AUTH_MODE],
                    CONF_USERNAME: normalized[CONF_USERNAME],
                    CONF_PASSWORD: normalized.get(CONF_PASSWORD),
                    CONF_REFRESH_TOKEN: normalized.get(CONF_REFRESH_TOKEN),
                    CONF_ACCOUNT_SEQ: normalized.get(CONF_ACCOUNT_SEQ),
                }
                options = {
                    CONF_SEPARATE_CONTROL: normalized[CONF_SEPARATE_CONTROL],
                    CONF_SOUND_ENABLED: normalized[CONF_SOUND_ENABLED],
                    CONF_SCAN_INTERVAL: normalized[CONF_SCAN_INTERVAL],
                }

                return self.async_create_entry(
                    title=f"Navien Smart ({normalized[CONF_USERNAME]})",
                    data=data,
                    options=options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return options flow."""

        return NavienSmartOptionsFlow(config_entry)

    async def _async_validate_and_normalize(
        self,
        user_input: dict[str, Any],
        errors: dict[str, str],
    ) -> dict[str, Any]:
        auth_mode = user_input[CONF_AUTH_MODE]
        username = str(user_input[CONF_USERNAME]).strip()
        password = str(user_input.get(CONF_PASSWORD, "")).strip() or None
        refresh_token = str(user_input.get(CONF_REFRESH_TOKEN, "")).strip() or None
        account_seq_input = user_input.get(CONF_ACCOUNT_SEQ)

        try:
            account_seq = int(account_seq_input) if account_seq_input not in (None, "") else None
        except (TypeError, ValueError):
            errors["base"] = "invalid_account_seq"
            return user_input

        if auth_mode == AUTH_MODE_ACCOUNT and not password:
            errors["base"] = "missing_password"
            return user_input

        if auth_mode == AUTH_MODE_TOKEN:
            if not refresh_token:
                errors["base"] = "missing_refresh_token"
                return user_input
            if account_seq is None:
                errors["base"] = "missing_account_seq"
                return user_input

        session = async_create_clientsession(self.hass)
        client = NavienApiClient(
            session=session,
            auth_mode=auth_mode,
            username=username,
            password=password,
            refresh_token=refresh_token,
            account_seq=account_seq,
            sound_enabled=bool(user_input.get(CONF_SOUND_ENABLED, DEFAULT_SOUND_ENABLED)),
        )

        try:
            await client.async_prepare()
        except NavienAuthError:
            errors["base"] = "invalid_auth"
            return user_input
        except NavienApiError:
            errors["base"] = "cannot_connect"
            return user_input
        except Exception:
            errors["base"] = "unknown"
            return user_input
        finally:
            await client.async_shutdown()

        normalized = dict(user_input)
        normalized[CONF_USERNAME] = client.user_id
        normalized[CONF_ACCOUNT_SEQ] = client.account_seq
        normalized[CONF_REFRESH_TOKEN] = client.refresh_token
        normalized[CONF_PASSWORD] = password
        normalized[CONF_SEPARATE_CONTROL] = bool(
            user_input.get(CONF_SEPARATE_CONTROL, DEFAULT_SEPARATE_CONTROL)
        )
        normalized[CONF_SOUND_ENABLED] = bool(
            user_input.get(CONF_SOUND_ENABLED, DEFAULT_SOUND_ENABLED)
        )
        normalized[CONF_SCAN_INTERVAL] = int(
            user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        return normalized


class NavienSmartOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Navien Smart."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_SEPARATE_CONTROL: bool(
                        user_input.get(
                            CONF_SEPARATE_CONTROL,
                            self._config_entry.options.get(
                                CONF_SEPARATE_CONTROL,
                                self._config_entry.data.get(
                                    CONF_SEPARATE_CONTROL,
                                    DEFAULT_SEPARATE_CONTROL,
                                ),
                            ),
                        )
                    ),
                    CONF_SOUND_ENABLED: bool(
                        user_input.get(
                            CONF_SOUND_ENABLED,
                            self._config_entry.options.get(
                                CONF_SOUND_ENABLED,
                                self._config_entry.data.get(
                                    CONF_SOUND_ENABLED,
                                    DEFAULT_SOUND_ENABLED,
                                ),
                            ),
                        )
                    ),
                    CONF_SCAN_INTERVAL: int(
                        user_input.get(
                            CONF_SCAN_INTERVAL,
                            self._config_entry.options.get(
                                CONF_SCAN_INTERVAL,
                                self._config_entry.data.get(
                                    CONF_SCAN_INTERVAL,
                                    DEFAULT_SCAN_INTERVAL,
                                ),
                            ),
                        )
                    ),
                },
            )

        current = {
            CONF_SEPARATE_CONTROL: self._config_entry.options.get(
                CONF_SEPARATE_CONTROL,
                self._config_entry.data.get(CONF_SEPARATE_CONTROL, DEFAULT_SEPARATE_CONTROL),
            ),
            CONF_SOUND_ENABLED: self._config_entry.options.get(
                CONF_SOUND_ENABLED,
                self._config_entry.data.get(CONF_SOUND_ENABLED, DEFAULT_SOUND_ENABLED),
            ),
            CONF_SCAN_INTERVAL: self._config_entry.options.get(
                CONF_SCAN_INTERVAL,
                self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ),
        }

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SEPARATE_CONTROL,
                    default=bool(current[CONF_SEPARATE_CONTROL]),
                ): bool,
                vol.Required(
                    CONF_SOUND_ENABLED,
                    default=bool(current[CONF_SOUND_ENABLED]),
                ): bool,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=int(current[CONF_SCAN_INTERVAL]),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=10,
                        mode="box",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    auth_default = defaults.get(CONF_AUTH_MODE, AUTH_MODE_ACCOUNT)

    return vol.Schema(
        {
            vol.Required(CONF_AUTH_MODE, default=auth_default): SelectSelector(
                SelectSelectorConfig(
                    options=[AUTH_MODE_ACCOUNT, AUTH_MODE_TOKEN],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="auth_mode",
                )
            ),
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Optional(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
            vol.Optional(CONF_REFRESH_TOKEN, default=defaults.get(CONF_REFRESH_TOKEN, "")): str,
            vol.Optional(CONF_ACCOUNT_SEQ, default=defaults.get(CONF_ACCOUNT_SEQ, "")): str,
            vol.Required(
                CONF_SEPARATE_CONTROL,
                default=defaults.get(CONF_SEPARATE_CONTROL, DEFAULT_SEPARATE_CONTROL),
            ): bool,
            vol.Required(
                CONF_SOUND_ENABLED,
                default=defaults.get(CONF_SOUND_ENABLED, DEFAULT_SOUND_ENABLED),
            ): bool,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=10,
                    mode="box",
                )
            ),
        }
    )
