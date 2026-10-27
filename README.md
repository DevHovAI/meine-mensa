# Meine Mensa

A Home Assistant integration and dashboard card for the meal plans of the
**Studentenwerk Halle** canteens (Halle, Merseburg, Köthen, Bernburg, Dessau, Burg),
as published on [meine-mensa.de](https://www.meine-mensa.de).

- Choose your canteens during setup; each one becomes a sensor
- Today and the next five days, refreshed every three hours
- A card that shows the next day with meals – with photos, sides, labels and prices
- Filter for **vegetarian** and **vegan** meals, as a setting or as buttons in the card
- Hide meals by word, e.g. `Schwein` or an allergen such as `Sellerie`
- The integration serves the card itself: no dashboard resource to add
- Texts follow the Home Assistant language (German or English)

meine-mensa.de has no public API; the integration reads the same page the website shows.
If the site changes its layout, the plan may stay empty until the integration is updated.

## Installation

### HACS

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/DevHovAI/meine-mensa` with type **Integration**.
3. Search for **Meine Mensa**, download it and restart Home Assistant.

### Manual

Copy `custom_components/meine_mensa` to `<config>/custom_components/` and restart
Home Assistant.

## Setup

*Settings → Devices & services → Add integration → Meine Mensa*, then tick your canteens.
To change them later: the integration's menu (⋮) → **Reconfigure**.

Each canteen gets a sensor such as `sensor.weinbergmensa_meals_today`. Its state is the
number of meals today; the attribute `days` holds the plan for the coming days. The
attribute is left out of the recorder.

## Card

Reload the browser once after installing, then *Add card → Meine Mensa*, or in YAML:

```yaml
type: custom:meine-mensa-card
entities:
  - sensor.weinbergmensa_meals_today
day: next
diet: vegetarian
```

| Option | Default | Description |
|---|---|---|
| `entities` | – | One or more Meine Mensa sensors. With several, each canteen gets its own section. |
| `title` | canteen name | Card title. |
| `day` | `next` | `next` (next day with meals after today, skips weekends), `tomorrow`, `today`, or `auto` (today until `switch_time`, then the next day). |
| `switch_time` | `14:30` | For `day: auto`. |
| `diet` | `all` | `all`, `vegetarian` (includes vegan) or `vegan`. |
| `show_filter` | `true` | Buttons *All / Vegetarian / Vegan* in the card. The choice is kept in the browser and overrides `diet`. |
| `price` | `students` | `students`, `staff`, `guests` or `none`. |
| `show_images` | `true` | Photo of the meal. |
| `show_sides` | `true` | Choice of sides. |
| `show_labels` | `true` | Labels such as vegan, poultry, climate plate. |
| `show_additives` | `false` | Allergens and additives. |
| `exclude` | – | Comma-separated words; meals containing one of them in the name, sides, labels or allergens are hidden. |

Vegetarian and vegan come from the canteen's own labels (`vegan`, `vegetarisch`,
`fleischlos`). A meal without a label counts as neither.

## Development

```sh
uv venv -p 3.14 .venv && uv pip install -p .venv -r requirements-dev.txt
just check
```

## License

MIT
