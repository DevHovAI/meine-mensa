import pytest

from custom_components.meine_mensa.api import (
    MensaError,
    _split_list,
    parse_food_plan,
    parse_start_page,
)


def test_start_page(start_page):
    token, canteens = parse_start_page(start_page)
    assert token == "TEST-CSRF-TOKEN"
    assert len(canteens) == 12
    # The site pads some names with spaces
    assert canteens[5] == "Weinbergmensa"


def test_start_page_without_list():
    with pytest.raises(MensaError):
        parse_start_page("<html><body>Wartungsarbeiten</body></html>")


def test_food_plan(food_plan):
    plan = parse_food_plan(food_plan)
    assert len(plan) == 12
    assert sum(len(m) for m in plan.values()) == 49

    bolognese, chicken = plan["Weinbergmensa"][:2]
    assert bolognese.name == "Soja-Gemüse-Bolognese mit Vollkornspaghetti"
    assert bolognese.vegan and bolognese.vegetarian
    assert bolognese.labels == ["vegan", "Sprint-Menü", "Klima-Teller"]
    assert bolognese.prices == {"students": 1.95, "staff": 4.95, "guests": 7.0}
    assert "enthält Soja (E)" in bolognese.additives
    assert bolognese.image.startswith("https://www.meine-mensa.de/mediathek/")

    assert not chicken.vegetarian
    assert chicken.sides == ["Pommes Frites", "Tomatenreis", "Brokkoli", "Leipziger Allerlei"]


def test_vegetarian_but_not_vegan(food_plan):
    meals = [m for ms in parse_food_plan(food_plan).values() for m in ms]
    assert any(m.vegetarian and not m.vegan for m in meals)


def test_empty_plan(empty_plan):
    assert parse_food_plan(empty_plan) == {}


def test_split_keeps_parentheses():
    assert _split_list("Kartoffelspalten, Spätzle (C,A1)") == ["Kartoffelspalten", "Spätzle (C,A1)"]
