from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from pathlib import Path

from .models import BirthData, Place


@dataclass(frozen=True)
class MorinusHor:
    name: str
    birth_date: date
    birth_time: time
    place: Place

    @property
    def birth_data(self) -> BirthData:
        return BirthData(self.birth_date, self.birth_time, self.place)


def _clean_token(token: str) -> str:
    token = token.strip()
    if token.startswith("."):
        token = token[1:]
    if token.startswith(("I", "V")):
        token = token[1:]
    return token


def _signed_coord(deg: int, minute: int, second: int, positive_flag: int) -> float:
    value = deg + minute / 60.0 + second / 3600.0
    return value if positive_flag else -value


def parse_hor_file(path: str | Path) -> MorinusHor:
    tokens = [_clean_token(part) for part in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()]
    tokens = [token for token in tokens if token and token != "." and token != "p0"]

    name = tokens[0]
    year = int(tokens[4])
    month = int(tokens[5])
    day = int(tokens[6])
    hour = int(tokens[7])
    minute = int(tokens[8])
    second = int(tokens[9])
    timezone_hours = int(tokens[13])
    timezone_minutes = int(tokens[15])
    timezone = "Asia/Seoul" if timezone_hours == 9 and timezone_minutes == 0 else f"{timezone_hours:+03d}:{timezone_minutes:02d}"

    place_idx = 16
    place_name = tokens[place_idx]
    lon_deg = int(tokens[place_idx + 1])
    lon_min = int(tokens[place_idx + 2])
    lon_sec = int(tokens[place_idx + 3])
    lon_positive = int(tokens[place_idx + 4])
    lat_deg = int(tokens[place_idx + 5])
    lat_min = int(tokens[place_idx + 6])
    lat_sec = int(tokens[place_idx + 7])
    lat_positive = int(tokens[place_idx + 8])

    place = Place(
        place_name,
        _signed_coord(lat_deg, lat_min, lat_sec, lat_positive),
        _signed_coord(lon_deg, lon_min, lon_sec, lon_positive),
        timezone,
    )
    return MorinusHor(name, date(year, month, day), time(hour, minute, second), place)
