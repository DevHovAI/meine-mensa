from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def start_page() -> str:
    return (FIXTURES / "index.html").read_text()


@pytest.fixture
def food_plan() -> str:
    return (FIXTURES / "foodplan.html").read_text()


@pytest.fixture
def empty_plan() -> str:
    return (FIXTURES / "foodplan-empty.html").read_text()
