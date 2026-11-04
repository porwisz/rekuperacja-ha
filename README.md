# Rekuperacja — Home Assistant

Automatyka wietrzenia nad encją `fan` rekuperatora (ESPHome, Tweetop EcoVent Recu 350).

Każdy moduł zgłasza żądanie wydajności; **wygrywa najwyższa**. Ręczna zmiana (panel, HA) wstrzymuje automatykę na ustawiony czas.

## Etap 1 (0.1.0)
- Harmonogram dzień/noc (osobne godziny w weekend): dzień = wydajność %, noc = preset **Sen**.
- Ręczne nadpisanie, przycisk Boost i „Powrót do automatyki”.
- Usługi `rekuperacja.request` (source, percentage | preset, minutes) i `rekuperacja.cancel` — dla własnych automatyzacji.

## Etap 2 (0.2.0)
- Prysznic: licznik wody ≥ 15 l **i** spadek CWU ≥ 2 °C w 3 min → 100%, wietrzenie 20 min po. Czujniki i progi w opcjach integracji.

Plany: kuchnia, przed spaniem, nieobecność/urlop — patrz `rekuperacja/06-integracja-hacs-plan.md` w repo SmartHome.

## Instalacja
HACS → Custom repositories → `porwisz/rekuperacja-ha` (Integration) → Rekuperacja → wybierz `fan.rekuperator`.

## Testy
```bash
uv venv -p 3.13 .venv && uv pip install -p .venv -r requirements_test.txt
.venv/bin/python -m pytest -q
```
