from __future__ import annotations

from .models import Place


DEFAULT_TIMEZONE = "Asia/Seoul"

_PLACES: dict[str, Place] = {
    "incheon": Place("Incheon", 37.4563, 126.7052, DEFAULT_TIMEZONE),
    "인천": Place("Incheon", 37.4563, 126.7052, DEFAULT_TIMEZONE),
    "seoul": Place("Seoul", 37.5665, 126.9780, DEFAULT_TIMEZONE),
    "서울": Place("Seoul", 37.5665, 126.9780, DEFAULT_TIMEZONE),
}


def resolve_place(name: str) -> Place:
    key = (name or "").strip().lower()
    if key in _PLACES:
        return _PLACES[key]
    raise KeyError(f"Unknown place: {name!r}")

