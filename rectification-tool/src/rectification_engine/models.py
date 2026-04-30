from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float
    timezone: str


@dataclass(frozen=True)
class BirthData:
    birth_date: date
    birth_time: time
    place: Place

    @classmethod
    def from_strings(cls, birth_date: str, birth_time: str, place_name: str) -> "BirthData":
        from .places import resolve_place

        y, m, d = [int(part) for part in birth_date.replace(".", "-").split("-")]
        hh, mm = [int(part) for part in birth_time.split(":")]
        return cls(
            birth_date=date(y, m, d),
            birth_time=time(hh, mm),
            place=resolve_place(place_name),
        )


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    birth_time: time


@dataclass(frozen=True)
class NatalPoint:
    name: str
    longitude: float
    latitude: float = 0.0
    speed_longitude: float = 0.0
    point_type: str = "planet"


@dataclass(frozen=True)
class MorinusPDHit:
    mode: str
    promissor: str
    direction: str
    significator: str
    aspect: str
    arc: Decimal
    hit_date_raw: str
    hit_date: date | None
    raw_line: str
