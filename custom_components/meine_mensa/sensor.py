from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import BASE_URL
from .const import DOMAIN
from .coordinator import MensaConfigEntry, MensaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MensaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MensaSensor(coordinator, canteen_id, name)
        for canteen_id, name in coordinator.canteens.items()
    )


class MensaSensor(CoordinatorEntity[MensaCoordinator], SensorEntity):
    """One canteen. State: number of meals today; the plan is in the "days" attribute."""

    _attr_has_entity_name = True
    _attr_translation_key = "meals_today"
    _attr_icon = "mdi:silverware-fork-knife"
    # The plan is several kilobytes and changes daily; history of it is of no use.
    _unrecorded_attributes = frozenset({"days"})

    def __init__(self, coordinator: MensaCoordinator, canteen_id: int, name: str) -> None:
        super().__init__(coordinator)
        self._canteen = name
        self._attr_unique_id = f"{canteen_id}_meals"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(canteen_id))},
            name=name,
            manufacturer="Studentenwerk Halle",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=BASE_URL,
        )

    @property
    def _days(self) -> list[dict]:
        return (self.coordinator.data or {}).get(self._canteen, [])

    @property
    def native_value(self) -> int:
        today = dt_util.now().date().isoformat()
        return next((len(d["meals"]) for d in self._days if d["date"] == today), 0)

    @property
    def extra_state_attributes(self) -> dict:
        return {"canteen": self._canteen, "days": self._days}
