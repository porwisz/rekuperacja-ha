"""Stałe integracji Rekuperacja."""

from datetime import time

DOMAIN = "rekuperacja"
CONF_FAN = "fan_entity"
CONF_WATER = "water_entity"
CONF_CWU = "cwu_entity"
CONF_MIN_LITERS = "shower_min_liters"
CONF_MIN_DROP = "shower_min_drop"

DEFAULT_WATER = "sensor.testowe_wodomierz_woda_stan_licznika"
DEFAULT_CWU = "sensor.cwu_temperatura_aktualna_dol"

PRESET_SLEEP = "Sen"
PRESET_BOOST = "Boost"

# Poziom porównawczy presetu Sen (najwyższa wydajność wygrywa).
SLEEP_LEVEL = 20
# Po wysłaniu komendy ignorujemy zmiany wentylatora przez tyle sekund (echo z ESPHome).
COMMAND_GRACE_S = 15
# Ta sama komenda nie jest ponawiana częściej niż co tyle sekund.
RESEND_INTERVAL_S = 300

SOURCE_MANUAL = "reczne"
SOURCE_SCHEDULE = "harmonogram"
SOURCE_BOOST_BUTTON = "przycisk_boost"
SOURCE_SHOWER = "prysznic"

DEFAULT_SETTINGS: dict = {
    "automation": True,
    "schedule_enabled": True,
    "day_percentage": 40,
    "manual_minutes": 60,
    "boost_minutes": 30,
    "shower_enabled": True,
    "shower_after_minutes": 20,
    "weekday_day_start": time(6, 0),
    "weekday_night_start": time(22, 30),
    "weekend_day_start": time(8, 0),
    "weekend_night_start": time(23, 30),
}

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.state"
SIGNAL_UPDATE = f"{DOMAIN}_update"
