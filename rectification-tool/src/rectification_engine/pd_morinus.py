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


def signed_short_arc(diff: float) -> float:
    direct = True
    if diff < 0.0:
        diff *= -1.0
        direct = False
    if diff > 180.0:
        diff = 360.0 - diff
        direct = not direct
    if not direct:
        diff *= -1.0
    return diff


def _zodiacal_md_sa(
    longitude: float,
    latitude: float,
    armc: float,
    place_latitude: float,
    obliquity: float,
) -> tuple[float, float, bool, bool]:
    ra, decl = ra_decl_from_ecliptic(longitude, latitude, obliquity)
    raic = norm360(armc + 180.0)

    eastern = True
    if armc > raic:
        if raic < ra < armc:
            eastern = False
    elif (raic < ra < 360.0) or (0.0 < ra < armc):
        eastern = False

    med = abs(armc - ra)
    if med > 180.0:
        med = 360.0 - med
    icd = abs(raic - ra)
    if icd > 180.0:
        icd = 360.0 - icd

    val = math.tan(math.radians(place_latitude)) * math.tan(math.radians(decl))
    if abs(val) > 1.0:
        raise ValueError("Zodiacal point cannot be directed at this latitude.")
    adlat = math.degrees(math.asin(val))
    dsa = 90.0 + adlat
    nsa = 90.0 - adlat

    above_horizon = med <= dsa
    if above_horizon:
        return med, dsa, above_horizon, eastern
    return icd, nsa, above_horizon, eastern


def _morinus_vars(above_horizon: bool, eastern: bool, armc: float) -> tuple[float, float, float]:
    t = -1.0
    if (eastern and not above_horizon) or (not eastern and above_horizon):
        t = 1.0

    v = 1.0
    ra = armc
    if not above_horizon:
        v = -1.0
        ra = norm360(armc + 180.0)
    return t, v, ra


def _context(birth: BirthData):
    swe = configure_swisseph()
    jd_ut = julian_day_ut(birth)
    _houses, ascmc = swe.houses_ex(jd_ut, birth.place.latitude, birth.place.longitude, b"P")
    armc = float(ascmc[2])
    obliquity = float(swe.calc_ut(jd_ut, swe.ECL_NUT)[0][0])
    return jd_ut, armc, obliquity


def zodiacal_promissor_aspect_to_mc(
    birth: BirthData,
    promissor_name: str,
    aspect_name: str,
    aspect_sign: int,
    points: dict[str, NatalPoint] | None = None,
) -> DirectionArc:
    points = points or expand_antiscia(calculate_natal_points(birth))
    promissor = points[promissor_name]

    _jd_ut, armc, obliquity = _context(birth)

    aspect = ASPECT_DEGREES[aspect_name] * aspect_sign
    aspect_longitude = norm360(promissor.longitude + aspect)
    ra, _decl = ra_decl_from_ecliptic(aspect_longitude, 0.0, obliquity)
    return morinus_create_arc(ra - armc)


def zodiacal_promissor_to_significator_aspect(
    birth: BirthData,
    promissor_name: str,
    significator_name: str,
    aspect_name: str,
    aspect_sign: int,
    points: dict[str, NatalPoint] | None = None,
) -> DirectionArc:
    points = points or expand_antiscia(calculate_natal_points(birth))
    promissor_name = _morinus_promissor_name(promissor_name)
    promissor = points[promissor_name]
    significator = points[significator_name]
    _jd_ut, armc, obliquity = _context(birth)

    ra_prom, decl_prom = ra_decl_from_ecliptic(promissor.longitude, 0.0, obliquity)
    significator_longitude = norm360(significator.longitude + ASPECT_DEGREES[aspect_name] * aspect_sign)
    return _zodiacal_arc_to_significator_longitude(
        birth=birth,
        ra_prom=ra_prom,
        decl_prom=decl_prom,
        significator_longitude=significator_longitude,
        armc=armc,
        obliquity=obliquity,
    )


def zodiacal_promissor_aspect_to_significator(
    birth: BirthData,
    promissor_name: str,
    aspect_name: str,
    aspect_sign: int,
    significator_name: str,
    points: dict[str, NatalPoint] | None = None,
) -> DirectionArc:
    points = points or expand_antiscia(calculate_natal_points(birth))
    promissor_name = _morinus_promissor_name(promissor_name)
    promissor = points[promissor_name]
    significator = points[significator_name]
    _jd_ut, armc, obliquity = _context(birth)

    promissor_longitude = norm360(promissor.longitude + ASPECT_DEGREES[aspect_name] * aspect_sign)
    ra_prom, decl_prom = ra_decl_from_ecliptic(promissor_longitude, 0.0, obliquity)
    return _zodiacal_arc_to_significator_longitude(
        birth=birth,
        ra_prom=ra_prom,
        decl_prom=decl_prom,
        significator_longitude=significator.longitude,
        armc=armc,
        obliquity=obliquity,
    )


def _zodiacal_arc_to_significator_longitude(
    birth: BirthData,
    ra_prom: float,
    decl_prom: float,
    significator_longitude: float,
    armc: float,
    obliquity: float,
) -> DirectionArc:
    val = math.tan(math.radians(birth.place.latitude)) * math.tan(math.radians(decl_prom))
    if abs(val) > 1.0:
        raise ValueError("Promissor cannot be directed at this latitude.")
    adprom = math.degrees(math.asin(val))

    md_sig, sa_sig, above_horizon, eastern = _zodiacal_md_sa(
        significator_longitude,
        0.0,
        armc,
        birth.place.latitude,
        obliquity,
    )
    t, v, ra = _morinus_vars(above_horizon, eastern, armc)
    raw_arc = signed_short_arc(ra_prom - ra) + t * (90.0 + v * adprom) * (md_sig / sa_sig)
    return morinus_create_arc(raw_arc)


def _morinus_promissor_name(name: str) -> str:
    # Morinus 8.1.0 reuses the antiscia RA/decl for Contraantiscion MC in
    # the zodiacal Asc/MC-to-planet path. Keep this compatibility shim narrow
    # until more Morinus fixture rows require a broader rule.
    if name == "Contraantiscion MC":
        return "Antiscion MC"
    return name
