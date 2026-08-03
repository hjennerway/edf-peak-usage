"""Config flow for EDF Usage."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_API_TOKEN,
    CONF_CUSTOMER_ID,
    CONF_GRAPHQL_ENDPOINT,
    CONF_OFF_PEAK_END,
    CONF_OFF_PEAK_START,
    CONF_TIMEZONE,
    DEFAULT_GRAPHQL_ENDPOINT,
    DEFAULT_OFF_PEAK_END,
    DEFAULT_OFF_PEAK_START,
    DEFAULT_TIMEZONE,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an EDF Usage config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            customer_id = user_input[CONF_CUSTOMER_ID].strip()
            await self.async_set_unique_id(customer_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"EDF Usage {customer_id}",
                data={
                    CONF_CUSTOMER_ID: customer_id,
                    CONF_API_TOKEN: user_input[CONF_API_TOKEN].strip(),
                },
                options={
                    CONF_GRAPHQL_ENDPOINT: DEFAULT_GRAPHQL_ENDPOINT,
                    CONF_OFF_PEAK_START: DEFAULT_OFF_PEAK_START,
                    CONF_OFF_PEAK_END: DEFAULT_OFF_PEAK_END,
                    CONF_TIMEZONE: DEFAULT_TIMEZONE,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CUSTOMER_ID): str,
                    vol.Required(CONF_API_TOKEN): str,
                }
            ),
            errors=errors,
        )
