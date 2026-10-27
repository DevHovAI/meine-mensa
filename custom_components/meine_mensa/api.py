"""Client for meine-mensa.de, the meal plans of Studentenwerk Halle.

The site has no API. The start page carries the list of canteens and a CSRF
token; the plan itself comes as an HTML fragment from a POST to /yummy/go.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from html.parser import HTMLParser

import aiohttp

BASE_URL = "https://www.meine-mensa.de"
PLAN_URL = f"{BASE_URL}/yummy/go"
TIMEOUT = aiohttp.ClientTimeout(total=30)

# Labels the site uses for meals without meat; "vegan" counts as vegetarian too.
VEGAN_LABELS = {"vegan"}
VEGETARIAN_LABELS = {"vegan", "vegetarisch", "fleischlos"}

_VOID = {"img", "br", "input", "meta", "link", "hr", "source"}
_PRICE = re.compile(r"\d+,\d{2}")


class MensaError(Exception):
    """meine-mensa.de could not be reached or answered with something unexpected."""


@dataclass
class Meal:
    name: str
    labels: list[str] = field(default_factory=list)
    sides: list[str] = field(default_factory=list)
    additives: list[str] = field(default_factory=list)
    prices: dict[str, float] = field(default_factory=dict)
    image: str | None = None
    vegan: bool = False
    vegetarian: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


class _Node:
    __slots__ = ("attrs", "children", "parent", "tag")

    def __init__(self, tag: str, attrs: dict[str, str], parent: _Node | None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[_Node | str] = []

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def elements(self) -> list[_Node]:
        return [c for c in self.children if isinstance(c, _Node)]

    def find_all(self, cls: str | None = None, tag: str | None = None) -> list[_Node]:
        found = []
        for child in self.elements():
            if (cls is None or cls in child.classes) and (tag is None or child.tag == tag):
                found.append(child)
            found.extend(child.find_all(cls, tag))
        return found

    def find(self, cls: str | None = None, tag: str | None = None) -> _Node | None:
        hits = self.find_all(cls, tag)
        return hits[0] if hits else None

    def text(self) -> str:
        parts = [c if isinstance(c, str) else c.text() for c in self.children]
        return " ".join(" ".join(parts).split())


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {}, None)
        self._current = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, {k: v or "" for k, v in attrs}, self._current)
        self._current.children.append(node)
        if tag not in _VOID:
            self._current = node

    def handle_startendtag(self, tag, attrs):
        self._current.children.append(_Node(tag, {k: v or "" for k, v in attrs}, self._current))

    def handle_endtag(self, tag):
        node = self._current
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self._current = node.parent

    def handle_data(self, data):
        if data.strip():
            self._current.children.append(data)


def _parse(html: str) -> _Node:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


def parse_start_page(html: str) -> tuple[str, dict[int, str]]:
    """Return the CSRF token and the canteens as {id: name}."""
    root = _parse(html)
    token = next(
        (m.attrs.get("content", "") for m in root.find_all(tag="meta")
         if m.attrs.get("name") == "csrf-token"),
        "",
    )
    canteens = {}
    for select in root.find_all(tag="select"):
        if select.attrs.get("id") != "location_id":
            continue
        for option in select.find_all(tag="option"):
            value = option.attrs.get("value", "")
            if value.isdigit():
                canteens[int(value)] = option.text()
    if not token or not canteens:
        raise MensaError("start page without CSRF token or canteen list")
    return token, canteens


def _split_list(text: str) -> list[str]:
    """Split "a, b (C,A1), c" at commas outside of parentheses."""
    items, depth, current = [], 0, ""
    for char in text:
        depth += (char == "(") - (char == ")")
        if char == "," and depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += char
    items.append(current.strip())
    return [i for i in items if i]


def _parse_meal(card: _Node) -> Meal | None:
    title = card.find("food_title")
    if title is None or not title.text():
        return None
    meal = Meal(name=title.text())

    for img in card.find_all(tag="img"):
        label = img.attrs.get("title", "").strip()
        if img.attrs.get("data-toggle") == "tooltip" and label and label not in meal.labels:
            meal.labels.append(label)
        elif "img-fluid" in img.classes and meal.image is None:
            meal.image = img.attrs.get("src") or None

    for block in card.find_all("small", "div"):
        heading = block.find("font-weight-bold")
        content = block.find("text-dark")
        if heading is None or content is None:
            continue
        name = heading.text().rstrip(":").strip()
        if name == "Wahlbeilagen":
            meal.sides = _split_list(content.text())
        elif name == "Zusatzstoffe":
            meal.additives = _split_list(content.text())

    prices = card.find("prices")
    if prices is not None:
        values = [float(v.replace(",", ".")) for v in _PRICE.findall(prices.text())]
        meal.prices = dict(zip(("students", "staff", "guests"), values, strict=False))

    lowered = {label.lower() for label in meal.labels}
    meal.vegan = bool(lowered & VEGAN_LABELS)
    meal.vegetarian = bool(lowered & VEGETARIAN_LABELS)
    return meal


def parse_food_plan(html: str) -> dict[str, list[Meal]]:
    """Return the meals per canteen name. Canteens without a plan are missing."""
    root = _parse(html)
    plan: dict[str, list[Meal]] = {}
    current: str | None = None
    # Header cards and meal rows alternate as siblings, one pair per canteen.
    for node in root.find_all():
        if "card-header" in node.classes:
            heading = node.find(tag="h5")
            current = heading.text().split("|")[0].strip() if heading else None
        elif "row-eq-height" in node.classes and current is not None:
            meals = [m for c in node.find_all("food-container") if (m := _parse_meal(c))]
            plan.setdefault(current, []).extend(meals)
    return plan


class MensaClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        # Own cookie jar: the CSRF token belongs to the site's session cookie.
        self._session = session
        self._token: str | None = None

    async def _start(self) -> dict[int, str]:
        html = await self._request("GET", BASE_URL)
        self._token, canteens = parse_start_page(html)
        return canteens

    async def _request(self, method: str, url: str, **kwargs) -> str:
        try:
            async with self._session.request(method, url, timeout=TIMEOUT, **kwargs) as resp:
                if resp.status == 419:
                    raise _TokenExpired
                resp.raise_for_status()
                return await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise MensaError(f"{method} {url}: {err}") from err

    async def canteens(self) -> dict[int, str]:
        return await self._start()

    async def food_plan(self, day: date, canteen_ids: list[int]) -> dict[str, list[Meal]]:
        data = [("date", day.strftime("%d.%m.%Y")), ("query", "foodplan")]
        data += [("location_ids[]", str(i)) for i in canteen_ids]
        for attempt in range(2):
            if self._token is None or attempt:
                await self._start()
            try:
                html = await self._request(
                    "POST", PLAN_URL, data=data, headers={"X-CSRF-TOKEN": self._token or ""}
                )
            except _TokenExpired:
                continue
            return parse_food_plan(html)
        raise MensaError("CSRF token rejected twice")


class _TokenExpired(Exception):
    pass
