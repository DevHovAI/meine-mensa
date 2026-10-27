from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.meine_mensa.api import BASE_URL, PLAN_URL
from custom_components.meine_mensa.const import CONF_CANTEENS, DOMAIN


def mock_site(aioclient_mock: AiohttpClientMocker, start_page: str, food_plan: str) -> None:
    aioclient_mock.get(BASE_URL, text=start_page)
    aioclient_mock.post(PLAN_URL, text=food_plan)


async def test_config_flow(hass: HomeAssistant, aioclient_mock, start_page, food_plan):
    mock_site(aioclient_mock, start_page, food_plan)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CANTEENS: []})
    assert result["errors"] == {"base": "no_canteen"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CANTEENS: ["5", "17"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_CANTEENS: {"5": "Weinbergmensa", "17": "Heidemensa"}}


async def test_config_flow_offline(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(BASE_URL, status=503)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_sensor(hass: HomeAssistant, aioclient_mock, start_page, food_plan):
    mock_site(aioclient_mock, start_page, food_plan)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_CANTEENS: {"5": "Weinbergmensa"}})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) == 1
    state = states[0]
    # The mock answers every day with the same plan
    assert state.state == "6"
    days = state.attributes["days"]
    assert len(days) == 6
    assert days[0]["meals"][0]["vegan"] is True
    # Every day was one request for all canteens
    posts = [call for call in aioclient_mock.mock_calls if call[0] == "POST"]
    assert len(posts) == 6


async def test_card_is_served(hass: HomeAssistant, aioclient_mock, hass_client, start_page, food_plan):
    mock_site(aioclient_mock, start_page, food_plan)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_CANTEENS: {"5": "Weinbergmensa"}})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    client = await hass_client()
    resp = await client.get("/meine_mensa/meine-mensa-card.js")
    assert resp.status == 200
    assert "meine-mensa-card" in await resp.text()
