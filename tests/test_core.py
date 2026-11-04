from datetime import datetime, time, timedelta

from custom_components.rekuperacja.const import DEFAULT_SETTINGS
from custom_components.rekuperacja.core.arbiter import Command, Request, resolve
from custom_components.rekuperacja.core.schedule import is_day

NOW = datetime(2026, 11, 4, 12, 0)  # środa


def test_max_level_wins():
    base = Request("harmonogram", 40, Command(percentage=40))
    boost = Request("prysznic", 100, Command(percentage=100), until=NOW + timedelta(minutes=5))
    assert resolve([base, boost], NOW) is boost


def test_expired_boost_ignored():
    base = Request("harmonogram", 40, Command(percentage=40))
    boost = Request("prysznic", 100, Command(percentage=100), until=NOW - timedelta(seconds=1))
    assert resolve([base, boost], NOW) is base


def test_manual_beats_higher():
    boost = Request("prysznic", 100, Command(percentage=100), until=NOW + timedelta(minutes=5))
    manual = Request("reczne", 20, Command(percentage=20), until=NOW + timedelta(minutes=60))
    assert resolve([boost], NOW, manual) is manual


def test_tie_prefers_timed():
    base = Request("harmonogram", 40, Command(percentage=40))
    timed = Request("x", 40, Command(preset="Boost"), until=NOW + timedelta(minutes=1))
    assert resolve([base, timed], NOW) is timed


def test_empty():
    assert resolve([], NOW) is None


def test_schedule_weekday_and_weekend():
    s = DEFAULT_SETTINGS
    assert is_day(NOW, s)
    assert not is_day(NOW.replace(hour=23), s)
    assert not is_day(NOW.replace(hour=5), s)
    sat = datetime(2026, 11, 7, 7, 0)
    assert not is_day(sat, s)  # weekend dzień od 8:00
    assert is_day(sat.replace(hour=23), s)


def test_schedule_over_midnight():
    s = dict(DEFAULT_SETTINGS, weekday_day_start=time(20, 0), weekday_night_start=time(2, 0))
    assert is_day(NOW.replace(hour=1), s)
    assert not is_day(NOW.replace(hour=12), s)


def test_shower_detector():
    from custom_components.rekuperacja.core.shower import ShowerDetector

    d = ShowerDetector()
    t0 = NOW
    for i in range(7):  # 8 l/min, CWU spada 0.5 °C/min
        t = t0 + timedelta(minutes=i * 0.5)
        d.add_water_liters(t, 1000 + i * 4)
        d.add_cwu(t, 49.5 - i * 0.5)
    assert d.detected(t0 + timedelta(minutes=3))
    assert not d.detected(t0 + timedelta(minutes=10))  # okno wygasło


def test_tap_not_shower():
    from custom_components.rekuperacja.core.shower import ShowerDetector

    d = ShowerDetector()
    for i in range(7):
        t = NOW + timedelta(minutes=i * 0.5)
        d.add_water_liters(t, 1000 + i * 2)  # 12 l / 3 min
        d.add_cwu(t, 49.5 - i * 0.5)
    assert not d.detected(NOW + timedelta(minutes=3))


def test_next_switch():
    from custom_components.rekuperacja.core.schedule import next_switch

    assert next_switch(NOW, DEFAULT_SETTINGS) == NOW.replace(hour=22, minute=30)
    assert next_switch(NOW.replace(hour=23), DEFAULT_SETTINGS) == datetime(2026, 11, 5, 6, 0)
    fri = datetime(2026, 11, 6, 23, 0)
    assert next_switch(fri, DEFAULT_SETTINGS) == datetime(2026, 11, 7, 8, 0)
