from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from .models import MorinusPDHit


ASPECTS = {
    "Conjunctio": "Conjunctio",
    "Sextil": "Sextil",
    "Quadrat": "Quadrat",
    "Trigon": "Trigon",
    "Oppositio": "Oppositio",
}

_ROW_RE = re.compile(
    r"^(?P<mode>[ZM])\s+"
    r"(?P<left>.+?)\s+"
    r"(?P<direction>[DC])\s+-->\s+"
    r"(?P<right>.+?)\s+"
    r"(?P<arc>\d+(?:\.\d+)?)\s+"
    r"(?P<date>\d{4}\.\d{2}\.\d{2})$"
)


def parse_morinus_pd_text(text: str) -> list[MorinusPDHit]:
    hits: list[MorinusPDHit] = []
    for line in text.splitlines():
        parsed = parse_morinus_pd_line(line)
        if parsed is not None:
            hits.append(parsed)
    return hits


def parse_morinus_pd_file(path: str | Path) -> list[MorinusPDHit]:
    return parse_morinus_pd_text(Path(path).read_text(encoding="utf-8-sig"))


def parse_morinus_pd_line(line: str) -> MorinusPDHit | None:
    raw_line = line.strip()
    if not raw_line or raw_line.startswith(("Placidian", "Static Key:", "Naibod")):
        return None

    match = _ROW_RE.match(raw_line)
    if not match:
        return None

    left = match.group("left").strip()
    right = match.group("right").strip()
    aspect, promissor, significator, aspect_side = _extract_aspect_and_points(left, right)
    raw_date = match.group("date")
    y, m, d = [int(part) for part in raw_date.split(".")]
    try:
        hit_date = date(y, m, d)
    except ValueError:
        hit_date = None

    return MorinusPDHit(
        mode=match.group("mode"),
        promissor=promissor,
        direction=match.group("direction"),
        significator=significator,
        aspect=aspect,
        aspect_side=aspect_side,
        arc=Decimal(match.group("arc")),
        hit_date_raw=raw_date,
        hit_date=hit_date,
        raw_line=raw_line,
    )


def _extract_aspect_and_points(left: str, right: str) -> tuple[str, str, str, str]:
    left_tokens = left.split()
    right_tokens = right.split()

    if left_tokens and left_tokens[0] in ASPECTS:
        return ASPECTS[left_tokens[0]], " ".join(left_tokens[1:]), right, "promissor"

    if right_tokens and right_tokens[0] in ASPECTS:
        return ASPECTS[right_tokens[0]], left, " ".join(right_tokens[1:]), "significator"

    return "Conjunctio", left, right, "none"
