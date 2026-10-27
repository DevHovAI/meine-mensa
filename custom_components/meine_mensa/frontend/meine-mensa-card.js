/*
 * Meine Mensa Card – meal plan of one or more canteens of Studentenwerk Halle.
 *
 * Reads the "days" attribute of the sensors from the Meine Mensa integration, which
 * also serves this file, so no dashboard resource is needed.
 * Colors come from the Home Assistant theme.
 */

const VERSION = "0.1.1";
const TAG = "meine-mensa-card";

const DEFAULTS = {
  entities: [],
  day: "next",
  switch_time: "14:30",
  diet: "all",
  show_filter: true,
  price: "students",
  show_images: true,
  show_sides: true,
  show_labels: true,
  show_additives: false,
  exclude: "",
};

const LABEL_ICONS = {
  vegan: "mdi:leaf",
  vegetarisch: "mdi:sprout",
  fleischlos: "mdi:sprout",
  fisch: "mdi:fish",
  "geflügel": "mdi:food-drumstick",
  schwein: "mdi:pig-variant",
  rind: "mdi:cow",
  wild: "mdi:deer",
  "klima-teller": "mdi:earth",
  "sprint-menü": "mdi:run-fast",
  "neue rezeptur": "mdi:star-four-points-outline",
  asiatisch: "mdi:noodles",
};

const VEG_LABELS = new Set(["vegan", "vegetarisch", "fleischlos"]);
const DIETS = ["all", "vegetarian", "vegan"];

const TEXTS = {
  en: {
    today: "Today",
    tomorrow: "Tomorrow",
    all: "All",
    vegetarian: "Vegetarian",
    vegan: "Vegan",
    none: "No meals on this day.",
    filtered: (n) => `No meals match the filter (${n} hidden).`,
    missing: "Add a Meine Mensa sensor in the card settings.",
    unavailable: "Meal plan not available.",
    sides: "Sides",
  },
  de: {
    today: "Heute",
    tomorrow: "Morgen",
    all: "Alle",
    vegetarian: "Vegetarisch",
    vegan: "Vegan",
    none: "An diesem Tag gibt es kein Essen.",
    filtered: (n) => `Kein Gericht passt zum Filter (${n} ausgeblendet).`,
    missing: "Wähle in den Karteneinstellungen einen Meine-Mensa-Sensor.",
    unavailable: "Speiseplan nicht verfügbar.",
    sides: "Beilagen",
  },
};

const LABELS = {
  entities: "Canteens (Meine Mensa sensors)",
  title: "Title (optional)",
  day: "Day",
  switch_time: "Switch to the next day at (for “today, then next”)",
  diet: "Filter",
  show_filter: "Filter buttons in the card",
  price: "Price",
  show_images: "Photos",
  show_sides: "Sides",
  show_labels: "Labels (vegan, poultry, …)",
  show_additives: "Allergens and additives",
  exclude: "Hide meals containing (comma-separated)",
};

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const isoDate = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

// A factory, because the class has to extend whatever HTMLElement is current (see define()).
const createCardClass = (Base) =>
  class MeineMensaCard extends Base {
    static getStubConfig(hass) {
      const sensor = Object.keys(hass?.states || {}).find(
        (id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes?.days),
      );
      return { entities: sensor ? [sensor] : [] };
    }

    static getConfigForm() {
      const select = (options) => ({ select: { mode: "dropdown", options } });
      return {
        schema: [
          { name: "entities", selector: { entity: { multiple: true, filter: { integration: "meine_mensa" } } } },
          { name: "title", selector: { text: {} } },
          {
            type: "grid",
            name: "",
            schema: [
              {
                name: "day",
                selector: select([
                  { value: "next", label: "Next day with meals" },
                  { value: "tomorrow", label: "Tomorrow" },
                  { value: "today", label: "Today" },
                  { value: "auto", label: "Today, then next" },
                ]),
              },
              { name: "switch_time", selector: { time: {} } },
            ],
          },
          {
            type: "grid",
            name: "",
            schema: [
              {
                name: "diet",
                selector: select([
                  { value: "all", label: "All meals" },
                  { value: "vegetarian", label: "Vegetarian (incl. vegan)" },
                  { value: "vegan", label: "Vegan" },
                ]),
              },
              {
                name: "price",
                selector: select([
                  { value: "students", label: "Students" },
                  { value: "staff", label: "Staff" },
                  { value: "guests", label: "Guests" },
                  { value: "none", label: "Hide" },
                ]),
              },
            ],
          },
          {
            type: "grid",
            name: "",
            schema: [
              { name: "show_filter", selector: { boolean: {} } },
              { name: "show_images", selector: { boolean: {} } },
              { name: "show_sides", selector: { boolean: {} } },
              { name: "show_labels", selector: { boolean: {} } },
              { name: "show_additives", selector: { boolean: {} } },
            ],
          },
          { name: "exclude", selector: { text: {} } },
        ],
        computeLabel: (s) => LABELS[s.name],
        computeHelper: (s) =>
          s.name === "exclude" ? "e.g. Schwein, Sellerie – matched against name, sides, labels and allergens" : undefined,
      };
    }

    setConfig(config) {
      const entities = config.entities ?? (config.entity ? [config.entity] : []);
      this._config = { ...DEFAULTS, ...config, entities };
      this._diet = this._loadDiet() ?? this._config.diet;
      this._lastKey = undefined;
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      // Only re-render when one of our sensors or the language changed.
      const key = [hass.language, ...this._config.entities.map((id) => hass.states[id]?.last_updated)].join("|");
      if (key !== this._lastKey) {
        this._lastKey = key;
        this._render();
      }
    }

    connectedCallback() {
      // The day can change without a sensor update (midnight, switch_time).
      this._timer = setInterval(() => this._render(), 5 * 60 * 1000);
    }

    disconnectedCallback() {
      clearInterval(this._timer);
    }

    getCardSize() {
      return 6;
    }

    getGridOptions() {
      return { columns: 12, min_columns: 4, rows: "auto" };
    }

    get _t() {
      return (this._hass?.language || "").startsWith("de") ? TEXTS.de : TEXTS.en;
    }

    // The filter chosen in the card is kept per browser, so a kiosk keeps its choice.
    get _storageKey() {
      return `meine-mensa-card:${this._config.entities.join(",")}:diet`;
    }

    _loadDiet() {
      if (!this._config.show_filter) return null;
      try {
        const diet = localStorage.getItem(this._storageKey);
        return DIETS.includes(diet) ? diet : null;
      } catch {
        return null;
      }
    }

    _setDiet(diet) {
      this._diet = diet;
      try {
        localStorage.setItem(this._storageKey, diet);
      } catch {
        /* private mode or blocked storage: keep the choice until reload */
      }
      this._render();
    }

    // Which plan to show from the sorted list of days with meals.
    _pickDay(days) {
      const now = new Date();
      const today = isoDate(now);
      const tomorrow = isoDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1));
      const next = days.find((d) => d.date > today);
      switch (this._config.day) {
        case "today":
          return { date: today, day: days.find((d) => d.date === today) };
        case "tomorrow":
          return { date: tomorrow, day: days.find((d) => d.date === tomorrow) };
        case "auto": {
          const [h, m] = String(this._config.switch_time || "14:30").split(":").map(Number);
          const before = now.getHours() * 60 + now.getMinutes() < h * 60 + (m || 0);
          const todays = days.find((d) => d.date === today);
          if (before && todays) return { date: today, day: todays };
          return { date: next?.date ?? tomorrow, day: next };
        }
        default:
          return { date: next?.date ?? tomorrow, day: next };
      }
    }

    _dayLabel(date) {
      const t = this._t;
      const now = new Date();
      const today = isoDate(now);
      const tomorrow = isoDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1));
      const [y, mo, d] = date.split("-").map(Number);
      const formatted = new Date(y, mo - 1, d).toLocaleDateString(this._hass?.language || undefined, {
        weekday: "long",
        day: "numeric",
        month: "numeric",
      });
      if (date === today) return `${t.today} · ${formatted}`;
      if (date === tomorrow) return `${t.tomorrow} · ${formatted}`;
      return formatted;
    }

    _matches(meal) {
      if (this._diet === "vegan" && !meal.vegan) return false;
      if (this._diet === "vegetarian" && !meal.vegetarian) return false;
      const words = String(this._config.exclude || "")
        .split(",")
        .map((w) => w.trim().toLowerCase())
        .filter(Boolean);
      if (!words.length) return true;
      const haystack = [meal.name, ...(meal.sides || []), ...(meal.labels || []), ...(meal.additives || [])]
        .join(" ")
        .toLowerCase();
      return !words.some((w) => haystack.includes(w));
    }

    _price(meal) {
      const value = meal.prices?.[this._config.price];
      if (this._config.price === "none" || value == null) return "";
      return value.toLocaleString(this._hass?.language || undefined, { style: "currency", currency: "EUR" });
    }

    _mealHtml(meal) {
      const c = this._config;
      const labels = c.show_labels
        ? (meal.labels || [])
            .map((l) => {
              const icon = LABEL_ICONS[l.toLowerCase()];
              const cls = VEG_LABELS.has(l.toLowerCase()) ? "veg" : "";
              return `<span class="label ${cls}">${icon ? `<ha-icon icon="${icon}"></ha-icon>` : ""}${esc(l)}</span>`;
            })
            .join("")
        : "";
      const image = c.show_images && meal.image ? `<img class="photo" src="${esc(meal.image)}" alt="" loading="lazy">` : "";
      const sides = c.show_sides && meal.sides?.length ? `<div class="sides">${esc(this._t.sides)}: ${esc(meal.sides.join(", "))}</div>` : "";
      const additives = c.show_additives && meal.additives?.length ? `<div class="additives">${esc(meal.additives.join(", "))}</div>` : "";
      const price = this._price(meal);
      return `
        <li class="meal${image ? "" : " no-photo"}">
          ${image}
          <div class="body">
            <div class="top">
              <span class="name">${esc(meal.name)}</span>
              ${price ? `<span class="price">${esc(price)}</span>` : ""}
            </div>
            ${sides}
            ${labels ? `<div class="labels">${labels}</div>` : ""}
            ${additives}
          </div>
        </li>`;
    }

    _canteenHtml(entityId, showName) {
      const t = this._t;
      const state = this._hass?.states[entityId];
      if (!state) return `<div class="empty">${esc(t.unavailable)} (${esc(entityId)})</div>`;
      const days = Array.isArray(state.attributes.days) ? state.attributes.days : [];
      const { date, day } = this._pickDay(days);
      const meals = day?.meals || [];
      const shown = meals.filter((m) => this._matches(m));
      let list;
      if (state.state === "unavailable") list = `<div class="empty">${esc(t.unavailable)}</div>`;
      else if (!meals.length) list = `<div class="empty">${esc(t.none)}</div>`;
      else if (!shown.length) list = `<div class="empty">${esc(t.filtered(meals.length))}</div>`;
      else list = `<ul>${shown.map((m) => this._mealHtml(m)).join("")}</ul>`;
      const name = state.attributes.canteen || state.attributes.friendly_name || entityId;
      return `
        <section>
          <div class="subhead">
            ${showName ? `<span class="canteen">${esc(name)}</span>` : ""}
            <span class="date">${esc(this._dayLabel(date))}</span>
          </div>
          ${list}
        </section>`;
    }

    _render() {
      if (!this._config) return;
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      const t = this._t;
      const c = this._config;
      const entities = c.entities;
      const many = entities.length > 1;
      const title = c.title || (!many && entities[0] ? this._hass?.states[entities[0]]?.attributes.canteen : "") || "";
      const chips = c.show_filter
        ? `<div class="chips">${DIETS
            .map((d) => `<button class="chip${this._diet === d ? " on" : ""}" data-diet="${d}">${esc(t[d])}</button>`)
            .join("")}</div>`
        : "";
      const body = entities.length
        ? entities.map((id) => this._canteenHtml(id, many)).join("")
        : `<div class="empty">${esc(t.missing)}</div>`;

      this.shadowRoot.innerHTML = `
        <style>${STYLE}</style>
        <ha-card>
          <div class="header">
            ${title ? `<div class="title">${esc(title)}</div>` : ""}
            ${chips}
          </div>
          ${body}
        </ha-card>`;
      this.shadowRoot.querySelectorAll(".chip").forEach((b) =>
        b.addEventListener("click", () => this._setDiet(b.dataset.diet)),
      );
    }
  };

const STYLE = `
  ha-card { padding: 12px 16px 16px; overflow: hidden; }
  .header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
  .title { font-size: 1.25rem; font-weight: 500; color: var(--primary-text-color); }
  .chips { display: flex; gap: 6px; }
  .chip {
    font: inherit; font-size: 0.8rem; cursor: pointer; padding: 4px 10px; border-radius: 999px;
    color: var(--secondary-text-color); background: transparent;
    border: 1px solid var(--divider-color);
  }
  .chip.on { color: var(--text-primary-color, #fff); background: var(--primary-color); border-color: var(--primary-color); }
  section + section { margin-top: 16px; }
  .subhead { display: flex; gap: 8px; align-items: baseline; margin: 12px 0 4px; }
  .canteen { font-weight: 500; color: var(--primary-text-color); }
  .date { font-size: 0.85rem; color: var(--secondary-text-color); }
  ul { list-style: none; margin: 0; padding: 0; }
  .meal { display: flex; gap: 12px; padding: 10px 0; border-top: 1px solid var(--divider-color); }
  .meal:first-child { border-top: none; }
  .photo { width: 72px; height: 54px; flex: none; object-fit: cover; border-radius: 6px; background: var(--secondary-background-color); }
  .body { flex: 1; min-width: 0; }
  .top { display: flex; gap: 8px; justify-content: space-between; align-items: baseline; }
  .name { color: var(--primary-text-color); line-height: 1.3; }
  .price { flex: none; font-variant-numeric: tabular-nums; color: var(--accent-color, var(--primary-color)); font-weight: 500; }
  .sides, .additives { font-size: 0.8rem; color: var(--secondary-text-color); margin-top: 2px; line-height: 1.3; }
  .additives { opacity: 0.8; }
  .labels { display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 4px; }
  .label { display: inline-flex; align-items: center; gap: 3px; font-size: 0.75rem; color: var(--secondary-text-color); }
  .label ha-icon { --mdc-icon-size: 14px; }
  .label.veg { color: var(--success-color, #43a047); }
  .empty { padding: 12px 0 4px; color: var(--secondary-text-color); }
`;

/**
 * browser_mod and card-tools load the @webcomponents/scoped-custom-element-registry
 * polyfill, which swaps window.customElements and window.HTMLElement. Anything defined
 * in the old registry is then unknown to HA ("Custom element doesn't exist"), and a
 * class extending the old HTMLElement is refused by the new one. So build the class
 * from the live globals and register again whenever the registry may have changed.
 */
const define = () => {
  const registry = window.customElements;
  if (registry && !registry.get(TAG)) registry.define(TAG, createCardClass(window.HTMLElement));
};
const retry = () => {
  try {
    define();
  } catch (_) {
    // A swap in the middle of a pass; the next one settles it.
  }
};

define();
[250, 1000, 2000, 4000, 8000, 15000, 30000, 60000].forEach((ms) => setTimeout(retry, ms));
window.addEventListener("location-changed", retry);
document.addEventListener("visibilitychange", retry);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === TAG)) {
  window.customCards.push({
    type: TAG,
    name: "Meine Mensa",
    description: "Meal plan of Studentenwerk Halle canteens with vegetarian and vegan filter",
    preview: true,
    documentationURL: "https://github.com/DevHovAI/meine-mensa",
  });
}
console.info(`%c MEINE-MENSA-CARD %c ${VERSION} `, "color:#fff;background:#4a7c3a", "");
