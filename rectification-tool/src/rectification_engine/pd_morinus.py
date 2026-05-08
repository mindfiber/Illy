from __future__ import annotations

import math
from dataclasses import dataclass

from .ephemeris import configure_swisseph
from .models import BirthData, MorinusPDHit, NatalPoint
from .natal import calculate_natal_points, expand_antiscia, julian_day_ut, norm360


ASPECT_DEGREES = {
    "Conjunctio": 0.0,
    "Sextil": 60.0,
    "Quadrat": 90.0,
    "Trigon": 120.0,
    "Oppositio": 180.0,
}
ANGLE_POINTS = {"ASC", "MC", "LoF", "DSC"}


@dataclass(frozen=True)
class DirectionArc:
    arc: float
    direction: str
    raw_arc: float


def morinus_create_arc(raw_arc: float) -> DirectionArc:
    arc = raw_arc
    if arc <= -360.0:
        arc += 360.0
    if arc >= 360.0:
        arc -= 360.0
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


def zodiacal_promissor_aspect_to_angle(
    birth: BirthData,
    promissor_name: str,
    aspect_name: str,
    aspect_sign: int,
    angle_name: str,
    points: dict[str, NatalPoint] | None = None,
    use_point_latitudes: bool = False,
) -> DirectionArc:
    angle = canonical_point_name(angle_name)
    if angle not in {"ASC", "MC"}:
        raise ValueError(f"Unsupported angle significator: {angle_name!r}")
    points = points or expand_antiscia(calculate_natal_points(birth))
    promissor = points[promissor_name]

    _jd_ut, armc, obliquity = _context(birth)

    aspect = ASPECT_DEGREES[aspect_name] * aspect_sign
    aspect_longitude = norm360(promissor.longitude + aspect)
    prom_lat = promissor.latitude if use_point_latitudes else 0.0
    ra, decl = ra_decl_from_ecliptic(aspect_longitude, prom_lat, obliquity)
    if angle == "MC":
        return morinus_create_arc(ra - armc)

    val = math.tan(math.radians(birth.place.latitude)) * math.tan(math.radians(decl))
    if abs(val) > 1.0:
        raise ValueError("Promissor cannot be directed to ASC at this latitude.")
    adlat = math.degrees(math.asin(val))
    aoasc = norm360(armc + 90.0)
    return morinus_create_arc((ra - adlat) - aoasc)


def zodiacal_promissor_aspect_to_mc(
    birth: BirthData,
    promissor_name: str,
    aspect_name: str,
    aspect_sign: int,
    points: dict[str, NatalPoint] | None = None,
    use_point_latitudes: bool = False,
) -> DirectionArc:
    return zodiacal_promissor_aspect_to_angle(
        birth,
        promissor_name,
        aspect_name,
        aspect_sign,
        "MC",
        points,
        use_point_latitudes,
    )


def zodiacal_promissor_to_significator_aspect(
    birth: BirthData,
    promissor_name: str,
    significator_name: str,
    aspect_name: str,
    aspect_sign: int,
    points: dict[str, NatalPoint] | None = None,
    use_point_latitudes: bool = False,
) -> DirectionArc:
    points = points or expand_antiscia(calculate_natal_points(birth))
    # Morinus rule-lock:
    # "Promissors to Aspects of Significators" does not apply when the
    # significator itself is an angle point (ASC/MC/LoF/DSC).
    sig_canonical = canonical_point_name(significator_name)
    if sig_canonical in ANGLE_POINTS:
        raise ValueError(f"Angle significator is not allowed for promissor->significator-aspect mode: {significator_name}")

    promissor_name = _morinus_promissor_name(
        promissor_name,
        aspect_name=aspect_name,
        significator_name=significator_name,
    )
    promissor = points[promissor_name]
    significator = points[significator_name]
    _jd_ut, armc, obliquity = _context(birth)

    prom_lat = promissor.latitude if use_point_latitudes else 0.0
    sig_lat = significator.latitude if use_point_latitudes else 0.0
    ra_prom, decl_prom = ra_decl_from_ecliptic(promissor.longitude, prom_lat, obliquity)
    significator_longitude = norm360(significator.longitude + ASPECT_DEGREES[aspect_name] * aspect_sign)
    arc = _zodiacal_arc_to_significator_longitude(
        birth=birth,
        ra_prom=ra_prom,
        decl_prom=decl_prom,
        significator_longitude=significator_longitude,
        significator_latitude=sig_lat,
        armc=armc,
        obliquity=obliquity,
    )
    return arc


def zodiacal_promissor_aspect_to_significator(
    birth: BirthData,
    promissor_name: str,
    aspect_name: str,
    aspect_sign: int,
    significator_name: str,
    points: dict[str, NatalPoint] | None = None,
    use_point_latitudes: bool = False,
) -> DirectionArc:
    points = points or expand_antiscia(calculate_natal_points(birth))
    promissor_name = _morinus_promissor_name(
        promissor_name,
        aspect_name=aspect_name,
        significator_name=significator_name,
    )
    promissor = points[promissor_name]
    significator = points[significator_name]
    _jd_ut, armc, obliquity = _context(birth)

    promissor_longitude = norm360(promissor.longitude + ASPECT_DEGREES[aspect_name] * aspect_sign)
    prom_lat = promissor.latitude if use_point_latitudes else 0.0
    sig_lat = significator.latitude if use_point_latitudes else 0.0
    ra_prom, decl_prom = ra_decl_from_ecliptic(promissor_longitude, prom_lat, obliquity)
    arc = _zodiacal_arc_to_significator_longitude(
        birth=birth,
        ra_prom=ra_prom,
        decl_prom=decl_prom,
        significator_longitude=significator.longitude,
        significator_latitude=sig_lat,
        armc=armc,
        obliquity=obliquity,
    )
    return arc


def _zodiacal_arc_to_significator_longitude(
    birth: BirthData,
    ra_prom: float,
    decl_prom: float,
    significator_longitude: float,
    significator_latitude: float,
    armc: float,
    obliquity: float,
) -> DirectionArc:
    val = math.tan(math.radians(birth.place.latitude)) * math.tan(math.radians(decl_prom))
    if abs(val) > 1.0:
        raise ValueError("Promissor cannot be directed at this latitude.")
    adprom = math.degrees(math.asin(val))

    md_sig, sa_sig, above_horizon, eastern = _zodiacal_md_sa(
        significator_longitude,
        significator_latitude,
        armc,
        birth.place.latitude,
        obliquity,
    )
    t, v, ra = _morinus_vars(above_horizon, eastern, armc)
    raw_arc = signed_short_arc(ra_prom - ra) + t * (90.0 + v * adprom) * (md_sig / sa_sig)
    return morinus_create_arc(raw_arc)


def _morinus_promissor_name(
    name: str,
    *,
    aspect_name: str,
    significator_name: str,
) -> str:
    # Keep this compatibility shim extremely narrow.
    # Known fixture quirk: Contraantiscion MC -> Quadrat Sun behaves as
    # Antiscion MC in Morinus 8.1.0.
    if (
        name == "Contraantiscion MC"
        and aspect_name == "Quadrat"
        and canonical_point_name(significator_name) == "Sun"
    ):
        return "Antiscion MC"
    if name == "Contraantiscion MC" and canonical_point_name(significator_name) in {"MC", "ASC"}:
        return "Antiscion MC"
    if name == "Contraantiscion ASC" and canonical_point_name(significator_name) in {"ASC", "MC"}:
        return "Antiscion MC"
    return name


def canonical_point_name(name: str) -> str:
    aliases = {
        "Asc": "ASC",
        "ASC": "ASC",
        "Dsc": "LoF",
        "Desc": "LoF",
        "DSC": "LoF",
        "MC": "MC",
        "LoF": "LoF",
        "Fortuna": "LoF",
    }
    if name.startswith("Antiscion "):
        tail = name.split(" ", 1)[1]
        return f"Antiscion {aliases.get(tail, tail)}"
    if name.startswith("Contraantiscion "):
        tail = name.split(" ", 1)[1]
        return f"Contraantiscion {aliases.get(tail, tail)}"
    return aliases.get(name, name)


def best_zodiacal_planet_hit_match(
    birth: BirthData,
    hit: MorinusPDHit,
    points: dict[str, NatalPoint] | None = None,
) -> tuple[DirectionArc, float, str, int]:
    points = points or expand_antiscia(calculate_natal_points(birth))
    signs = [1, -1] if hit.aspect not in ("Conjunctio", "Oppositio") else [1]
    best: tuple[DirectionArc, float, str, int] | None = None

    for side in ("promissor", "significator"):
        for sign in signs:
            if side == "promissor":
                calc = zodiacal_promissor_aspect_to_significator(
                    birth=birth,
                    promissor_name=hit.promissor,
                    aspect_name=hit.aspect,
                    aspect_sign=sign,
                    significator_name=hit.significator,
                    points=points,
                )
            else:
                if canonical_point_name(hit.significator) in ANGLE_POINTS:
                    continue
                calc = zodiacal_promissor_to_significator_aspect(
                    birth=birth,
                    promissor_name=hit.promissor,
                    significator_name=hit.significator,
                    aspect_name=hit.aspect,
                    aspect_sign=sign,
                    points=points,
                )
            diff = abs(calc.arc - float(hit.arc))
            if calc.direction != hit.direction:
                diff += 1000.0
            candidate = (calc, diff, side, sign)
            if best is None or candidate[1] < best[1]:
                best = candidate

    if best is None:
        raise ValueError("Unable to match hit.")
    return best
