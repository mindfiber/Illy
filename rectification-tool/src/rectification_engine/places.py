from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .models import Place


DEFAULT_TIMEZONE = "Asia/Seoul"

_PLACES: dict[str, Place] = {
    "incheon": Place("Incheon", 37.4563, 126.7052, DEFAULT_TIMEZONE),
    "인천": Place("Incheon", 37.4563, 126.7052, DEFAULT_TIMEZONE),
    "morinus_0345": Place("Morinus 0345", 37.4333333333, 126.6666666667, DEFAULT_TIMEZONE),
    "seoul": Place("Seoul", 37.5665, 126.9780, DEFAULT_TIMEZONE),
    "서울": Place("Seoul", 37.5665, 126.9780, DEFAULT_TIMEZONE),
}

_MORINUS_PLACE_ALIASES = {
    "incheon": "icn",
    "인천": "icn",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _normalize_place_key(name: str) -> str:
    return re.sub(r"[\s_\-.,]+", "", (name or "").strip().lower())


def _parse_coord(value: str) -> float:
    match = re.fullmatch(r"(\d+)([EWNS])(\d+)", value.strip(), flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid Morinus coordinate: {value!r}")
    degrees = int(match.group(1))
    direction = match.group(2).upper()
    minutes = int(match.group(3))
    decimal = degrees + minutes / 60.0
    if direction in {"W", "S"}:
        decimal *= -1.0
    return decimal


def _timezone_name(offset: str) -> str:
    if offset == "+9:00":
        return DEFAULT_TIMEZONE
    return offset


@lru_cache(maxsize=1)
def _morinus_places() -> dict[str, Place]:
    path = _project_root() / "MorinusWinEng2.7" / "Res" / "placedb.dat"
    if not path.exists():
        return {}

    places: dict[str, Place] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.replace("\\u000a", "").strip()
        if not line or line == "." or line == "p0":
            continue
        if not (line.startswith("V#") or line.startswith(".V")):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        city = parts[0][2:].strip()
        longitude = _parse_coord(parts[1])
        latitude = _parse_coord(parts[2])
        timezone = _timezone_name(parts[3].strip())
        places[_normalize_place_key(city)] = Place(city, latitude, longitude, timezone)
    return places


def resolve_place(name: str) -> Place:
    normalized_key = _normalize_place_key(name)
    morinus_places = _morinus_places()
    morinus_place = morinus_places.get(_MORINUS_PLACE_ALIASES.get(normalized_key, normalized_key))
    if morinus_place is not None:
        return morinus_place

    key = (name or "").strip().lower()
    if key in _PLACES:
        return _PLACES[key]
    raise KeyError(f"Unknown place: {name!r}")
