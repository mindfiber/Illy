from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from rectification_engine.models import BirthData, NatalPoint
from rectification_engine.morinus_parser import parse_morinus_pd_file
from rectification_engine.natal import calculate_natal_points, expand_antiscia, norm360
from rectification_engine.pd_morinus import (
    zodiacal_promissor_aspect_to_mc,
    zodiacal_promissor_aspect_to_significator,
    zodiacal_promissor_to_significator_aspect,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "candidate_vs_morinus_diff.csv"

ASPECTS = ["Conjunctio", "Sextil", "Quadrat", "Trigon", "Oppositio"]
SIGNS = [1, -1]
NAIBOD = 0.9855555556
BASE_PROMISSORS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "LoF", "ASC", "MC"]
SIGNIFICATORS = ["ASC", "MC", "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "LoF"]


@dataclass(frozen=True)
class CandidateFile:
    hhmm: str
    file_path: Path


def arc_to_date(birth_dt: datetime, arc: float) -> str:
    days = (arc / NAIBOD) * 365.2422 - 2.15
    return (birth_dt + timedelta(days=days)).date().isoformat()


def allowed_promissors(points: dict[str, NatalPoint]) -> list[str]:
    names: list[str] = []
    for p in BASE_PROMISSORS:
        if p in points:
            names.append(p)
            a = f"Antiscion {p}"
            c = f"Contraantiscion {p}"
            if a in points:
                names.append(a)
            if c in points:
                names.append(c)
    return names


def generate_engine_rows(hhmm: str) -> list[dict]:
    birth = BirthData.from_strings("1976.1.22", f"{hhmm}:00", "seoul")
    birth_dt = datetime.combine(birth.birth_date, birth.birth_time)
    points = expand_antiscia(calculate_natal_points(birth)).copy()
    points["DSC"] = NatalPoint("DSC", norm360(points["ASC"].longitude + 180.0), point_type="angle")
    promissors = allowed_promissors(points)

    rows = []
    for p in promissors:
        for s in SIGNIFICATORS:
            if s not in points:
                continue
            for asp in ASPECTS:
                signs = [1] if asp in {"Conjunctio", "Oppositio"} else SIGNS
                for sg in signs:
                    try:
                        c = zodiacal_promissor_aspect_to_significator(birth, p, asp, sg, s, points)
                        rows.append(
                            {
                                "mode": "Z",
                                "promissor": p,
                                "aspect": asp,
                                "significator": s,
                                "direction": c.direction,
                                "pd_date": arc_to_date(birth_dt, c.arc),
                                "aspect_side": "promissor",
                            }
                        )
                    except Exception:
                        pass
                    try:
                        c = zodiacal_promissor_to_significator_aspect(birth, p, s, asp, sg, points)
                        rows.append(
                            {
                                "mode": "Z",
                                "promissor": p,
                                "aspect": asp,
                                "significator": s,
                                "direction": c.direction,
                                "pd_date": arc_to_date(birth_dt, c.arc),
                                "aspect_side": "significator",
                            }
                        )
                    except Exception:
                        pass
        for asp in ASPECTS:
            signs = [1] if asp in {"Conjunctio", "Oppositio"} else SIGNS
            for sg in signs:
                try:
                    c = zodiacal_promissor_aspect_to_mc(birth, p, asp, sg, points)
                    rows.append(
                        {
                            "mode": "Z",
                            "promissor": p,
                            "aspect": asp,
                            "significator": "MC",
                            "direction": c.direction,
                            "pd_date": arc_to_date(birth_dt, c.arc),
                            "aspect_side": "promissor",
                        }
                    )
                except Exception:
                    pass
    return rows


def main() -> None:
    targets = [
        CandidateFile("20:58", Path(r"C:/Users/com/Desktop/2058.txt")),
        CandidateFile("21:01", Path(r"C:/Users/com/Desktop/2101.txt")),
        CandidateFile("20:48", Path(r"C:/Users/com/Desktop/2048.txt")),
    ]

    out_rows = []
    reason_counter = Counter()

    for t in targets:
        mor = parse_morinus_pd_file(t.file_path)
        mor_keys_full = {
            (h.mode, h.promissor, h.aspect, h.significator, h.direction, h.hit_date.isoformat() if h.hit_date else "", h.aspect_side)
            for h in mor
        }
        mor_keys_wo_date = {(k[0], k[1], k[2], k[3], k[4], k[6]) for k in mor_keys_full}
        mor_modes = {h.mode for h in mor}

        eng = generate_engine_rows(t.hhmm)
        for r in eng:
            key_full = (r["mode"], r["promissor"], r["aspect"], r["significator"], r["direction"], r["pd_date"], r["aspect_side"])
            key_no_date = (r["mode"], r["promissor"], r["aspect"], r["significator"], r["direction"], r["aspect_side"])
            if key_full in mor_keys_full:
                reason = "exact_match"
            elif key_no_date in mor_keys_wo_date:
                reason = "date_mismatch_only"
            elif r["mode"] not in mor_modes:
                reason = "mode_not_present"
            else:
                reason = "signature_not_in_morinus"
            reason_counter[reason] += 1
            out_rows.append(
                {
                    "candidate_time": t.hhmm,
                    "promissor": r["promissor"],
                    "aspect": r["aspect"],
                    "significator": r["significator"],
                    "direction": r["direction"],
                    "pd_date": r["pd_date"],
                    "aspect_side": r["aspect_side"],
                    "compare_result": reason,
                }
            )

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    print(OUT)
    for k, v in reason_counter.most_common():
        print(k, v)


if __name__ == "__main__":
    main()

