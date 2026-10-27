from datetime import timedelta

DOMAIN = "meine_mensa"
CONF_CANTEENS = "canteens"

# Today plus the next days, so that "next day with meals" reaches over weekends and holidays.
DAYS_AHEAD = 5
UPDATE_INTERVAL = timedelta(hours=3)

CARD_URL = "/meine_mensa/meine-mensa-card.js"
