from __future__ import annotations

from pathlib import Path


DEFAULT_EPHEMERIS_PATHS = [
    Path("E:/Sujin/Illy/ZET 8/Swiss"),
]


def find_ephemeris_path() -> Path | None:
    for path in DEFAULT_EPHEMERIS_PATHS:
        if (path / "sepl_18.se1").exists() and (path / "semo_18.se1").exists():
            return path
    return None


def configure_swisseph(ephemeris_path: str | Path | None = None):
    try:
        import swisseph as swe
    except ImportError as exc:
        raise RuntimeError(
            "PySwissEph is not installed for this Python interpreter. "
            "Use Python 3.11 on this machine or install pyswisseph."
        ) from exc

    path = Path(ephemeris_path) if ephemeris_path is not None else find_ephemeris_path()
    if path is not None:
        swe.set_ephe_path(str(path))
    return swe

