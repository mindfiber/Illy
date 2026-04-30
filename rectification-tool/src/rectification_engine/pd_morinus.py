from __future__ import annotations

import math
from dataclasses import dataclass

from .ephemeris import configure_swisseph
from .models import BirthData, NatalPoint
from .natal import calculate_natal_points, expand_antiscia, julian_day_ut, norm360


ASPECT_DEGREES = {
    "Conjunctio": 0.0,
    "Sextil": 60.0,
    "Quadrat": 90.0,
    "Trigon": 120.0,
    "Oppositio": 180.0,
}


@dataclass(frozen=True)
class DirectionArc:
    arc: float
    direction: str
    raw_arc: float


def morinus_create_arc(raw_arc: float) -> DirectionArc:
    arc = raw_arc
    direct = True
    if arc < 0.0:
        arc *= -1.0
        direct = False
    if arc > 180.0:
        arc = 360.0 - arc
        direct = not direct
    return DirectionArc(arc=arc, direction="D" if direct else "C", raw_arc=raw_arc)


def ra_decl_from_ecliptic(longitude: float, latitude: float, obliquity: float) -> tuple[float, float]:
    lon = math.radians(norm360(longitude))
    lat = math.radians(latitude)
    eps = math.radians(obliquity)

    sin_decl = math.sin(lat) * math.cos(eps) + math.cos(lat) * math.sin(eps) * math.sin(lon)
    decl = math.asin(sin_decl)

    y = math.sin(lon) * math.cos(eps) - math.tan(lat) * math.sin(eps)
    x = math.cos(lon)
    ra = math.atan2(y, x)
    return norm360(math.degrees(ra)), math.degrees(decl)


def zodiacal_promissor_aspect_to_mc(
    birth: BirthData,
    promissor_name: str,
    aspect_name: str,
    aspect_sign: int,
    points: dict[str, NatalPoint] | None = None,
) -> DirectionArc:
    swe = configure_swisseph()
    jd_ut = julian_day_ut(birth)
    points = points or expand_antiscia(calculate_natal_points(birth))
    promissor = points[promissor_name]

    _houses, ascmc = swe.houses_ex(jd_ut, birth.place.latitude, birth.place.longitude, b"P")
    armc = float(ascmc[2])
    obliquity = float(swe.calc_ut(jd_ut, swe.ECL_NUT)[0][0])

    aspect = ASPECT_DEGREES[aspect_name] * aspect_sign
    aspect_longitude = norm360(promissor.longitude + aspect)
    ra, _decl = ra_decl_from_ecliptic(aspect_longitude, 0.0, obliquity)
    return morinus_create_arc(ra - armc)

