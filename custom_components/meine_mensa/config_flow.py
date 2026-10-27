from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import MensaClient, MensaError
from .const import CONF_CANTEENS, DOMAIN


class MensaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._canteens: dict[int, str] = {}

    async def _load_canteens(self) -> None:
        if not self._canteens:
            client = MensaClient(async_create_clientsession(self.hass))
            self._canteens = await client.canteens()

    def _schema(self, selected: list[str]) -> vol.Schema:
        options = [
            SelectOptionDict(value=str(i), label=name)
            for i, name in sorted(self._canteens.items(), key=lambda item: item[1])
        ]
        return vol.Schema(
            {
                vol.Required(CONF_CANTEENS, default=selected): SelectSelector(
                    SelectSelectorConfig(
                        options=options, multiple=True, mode=SelectSelectorMode.LIST
                    )
                )
            }
        )

    async def _step(
        self, step_id: str, user_input: dict[str, Any] | None, selected: list[str]
    ) -> tuple[dict[str, str] | None, ConfigFlowResult | None]:
        """Return the chosen canteens as {id: name}, or the form/abort to show instead."""
        errors: dict[str, str] = {}
        try:
            await self._load_canteens()
        except MensaError:
            return None, self.async_abort(reason="cannot_connect")
        if user_input is not None:
            chosen = [i for i in user_input[CONF_CANTEENS] if int(i) in self._canteens]
            if chosen:
                return {i: self._canteens[int(i)] for i in chosen}, None
            errors["base"] = "no_canteen"
            selected = []
        form = self.async_show_form(
            step_id=step_id, data_schema=self._schema(selected), errors=errors
        )
        return None, form

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        chosen, form = await self._step("user", user_input, [])
        if chosen is None:
            return form
        return self.async_create_entry(title="Meine Mensa", data={CONF_CANTEENS: chosen})

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        chosen, form = await self._step("reconfigure", user_input, list(entry.data[CONF_CANTEENS]))
        if chosen is None:
            return form
        return self.async_update_reload_and_abort(entry, data={CONF_CANTEENS: chosen})
