from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import MensaClient, MensaError
from .const import CONF_CANTEENS, DAYS_AHEAD, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type MensaConfigEntry = ConfigEntry[MensaCoordinator]


class MensaCoordinator(DataUpdateCoordinator[dict[str, list[dict]]]):
    """Fetches all selected canteens in one request per day.

    Data: {canteen name: [{"date": "YYYY-MM-DD", "meals": [...]}, ...]}
    """

    def __init__(self, hass: HomeAssistant, entry: MensaConfigEntry, client: MensaClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        # {id: name}, stored by the config flow
        self.canteens: dict[int, str] = {
            int(k): v for k, v in entry.data[CONF_CANTEENS].items()
        }

    async def _async_update_data(self) -> dict[str, list[dict]]:
        today = dt_util.now().date()
        data: dict[str, list[dict]] = {name: [] for name in self.canteens.values()}
        try:
            for offset in range(DAYS_AHEAD + 1):
                day = today + timedelta(days=offset)
                plan = await self.client.food_plan(day, list(self.canteens))
                for name, meals in plan.items():
                    if name in data and meals:
                        data[name].append(
                            {"date": day.isoformat(), "meals": [m.as_dict() for m in meals]}
                        )
        except MensaError as err:
            raise UpdateFailed(str(err)) from err
        return data
