from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .ephemeris import configure_swisseph
from .models import BirthData, NatalPoint


PLANET_IDS = {
    "Sun": "SUN",
    "Moon": "MOON",
    "Mercury": "MERCURY",
    "Venus": "VENUS",
    "Mars": "MARS",
    "Jupiter": "JUPITER",
    "Saturn": "SATURN",
}


def norm360(value: float) -> float:
    result = value % 360.0
    if result < 0:
        result += 360.0
    return result


def antiscia(longitude: float) -> float:
    lon = norm360(longitude)
    if lon < 180.0:
        return norm360(180.0 - lon)
    return norm360(540.0 - lon)


def contra_antiscia(longitude: float) -> float:
    return norm360(antiscia(longitude) + 180.0)


def julian_day_ut(birth: BirthData) -> float:
    swe = configure_swisseph()
    local_dt = datetime.combine(birth.birth_date, birth.birth_time, tzinfo=ZoneInfo(birth.place.timezone))
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    hour = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0 + utc_dt.microsecond / 3_600_000_000.0
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, hour)


def calculate_natal_points(birth: BirthData) -> dict[str, NatalPoint]:
    swe = configure_swisseph()
    jd_ut = julian_day_ut(birth)

    points: dict[str, NatalPoint] = {}
    for name, attr in PLANET_IDS.items():
        planet_id = getattr(swe, attr)
        values, _flags = swe.calc_ut(jd_ut, planet_id)
        points[name] = NatalPoint(
            name=name,
            longitude=norm360(float(values[0])),
            latitude=float(values[1]),
            speed_longitude=float(values[3]),
            point_type="planet",
        )

    houses, ascmc = swe.houses_ex(
        jd_ut,
        birth.place.latitude,
        birth.place.longitude,
        b"P",
    )
    asc = norm360(float(ascmc[0]))
    mc = norm360(float(ascmc[1]))

    points["ASC"] = NatalPoint("ASC", asc, point_type="angle")
    points["MC"] = NatalPoint("MC", mc, point_type="angle")
    points["LoF"] = NatalPoint("LoF", lot_of_fortune(asc, points["Sun"].longitude, points["Moon"].longitude), point_type="angle")

    return points


def lot_of_fortune(asc: float, sun: float, moon: float) -> float:
    if is_day_chart(asc, sun):
        return norm360(asc + moon - sun)
    return norm360(asc + sun - moon)


def is_day_chart(asc: float, sun: float) -> bool:
    # Ecliptic longitudes between ASC and DSC are below the horizon.
    return norm360(sun - asc) >= 180.0


def expand_antiscia(points: dict[str, NatalPoint]) -> dict[str, NatalPoint]:
    expanded: dict[str, NatalPoint] = {}
    for point in points.values():
        expanded[point.name] = point
        expanded[f"Antiscion {point.name}"] = NatalPoint(
            name=f"Antiscion {point.name}",
            longitude=antiscia(point.longitude),
            point_type=f"{point.point_type}_antiscia",
        )
        expanded[f"Contraantiscion {point.name}"] = NatalPoint(
            name=f"Contraantiscion {point.name}",
            longitude=contra_antiscia(point.longitude),
            point_type=f"{point.point_type}_contra_antiscia",
        )
    return expanded
