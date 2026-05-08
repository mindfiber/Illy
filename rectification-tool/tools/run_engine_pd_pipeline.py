from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
from pathlib import Path

from rectification_engine.models import BirthData
from rectification_engine.morinus_parser import parse_morinus_pd_file
from rectification_engine.natal import calculate_natal_points, expand_antiscia
from rectification_engine.pd_morinus import (
    canonical_point_name,
    zodiacal_promissor_aspect_to_mc,
    zodiacal_promissor_aspect_to_significator,
    zodiacal_promissor_to_significator_aspect,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "morinus_0325_0405"
EVENTS_PATH = ROOT / "input" / "illy_personal_events.json"
OUT_COMPARE = ROOT / "output" / "engine_pd_vs_original_0330_0400_period_only_v6.csv"
OUT_FULL = ROOT / "output" / "engine_pd_event_matches_full_period_only_v6.csv"
OUT_SHORT = ROOT / "output" / "engine_pd_candidate_shortlist_period_only_v6.csv"

ASPECTS = {"Conjunctio", "Sextil", "Quadrat", "Trigon", "Oppositio"}
NAIBOD = 0.9855555556
ANGLE_POINTS = {"Asc", "ASC", "MC", "LoF", "Fortuna"}
HIGH_PRIORITY_TYPES = {
    "university_admission",
    "employment_start",
    "career_honor_event",
    "surgery_medical_major",
    "family_death",
    "marriage",
    "childbirth",
}

TYPE_PLANETS = {
    "university_admission": {"Sun", "Jupiter", "Venus"},
    "employment_start": {"Sun", "Jupiter", "Venus"},
    "career_honor_event": {"Sun", "Jupiter", "Venus"},
    "employment_end": {"Mars", "Saturn"},
    "loss_general": {"Mars", "Saturn"},
    "mental_health_crisis": {"Mars", "Saturn"},
    "surgery_medical_major": {"Mars", "Saturn"},
}

EVENT_RULES = {
    "university_admission": {"good_aspects": {"Conjunctio", "Sextil", "Trigon"}, "angle_targets": {"MC", "ASC", "LoF"}},
    "employment_start": {"good_aspects": {"Conjunctio", "Sextil", "Trigon"}, "angle_targets": {"MC", "ASC", "LoF"}},
    "career_honor_event": {"good_aspects": {"Conjunctio", "Sextil", "Trigon"}, "angle_targets": {"MC", "ASC", "LoF"}},
    "employment_end": {"hard_aspects": {"Conjunctio", "Quadrat", "Oppositio"}, "angle_targets": {"MC", "ASC", "LoF"}},
    "loss_general": {"hard_aspects": {"Conjunctio", "Quadrat", "Oppositio"}, "angle_targets": {"MC", "ASC", "LoF"}},
    "mental_health_crisis": {"hard_aspects": {"Conjunctio", "Quadrat", "Oppositio"}, "angle_targets": {"MC", "ASC", "LoF"}},
    "surgery_medical_major": {"hard_aspects": {"Conjunctio", "Quadrat", "Oppositio"}, "angle_targets": {"MC", "ASC", "LoF"}},
}


@dataclass(frozen=True)
class Event:
    event_id: str
    start_date: date
    end_date: date
    event_type: str
    text: str


def parse_event_date_window(s: str) -> tuple[date, date]:
    s = s.strip()
    if len(s) == 10:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return d, d
    if len(s) == 7:
        y, m = [int(x) for x in s.split("-")]
        start = date(y, m, 1)
        if m == 12:
            end = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(y, m + 1, 1) - timedelta(days=1)
        return start, end
    raise ValueError(f"Unsupported date format: {s}")


def day_distance_to_window(target: date, start: date, end: date) -> int:
    if target < start:
        return (start - target).days
    if target > end:
        return (target - end).days
    return 0


def minute_keys(start_hhmm: str, end_hhmm: str) -> list[str]:
    sh, sm = [int(x) for x in start_hhmm.split(":")]
    eh, em = [int(x) for x in end_hhmm.split(":")]
    s = sh * 60 + sm
    e = eh * 60 + em
    return [f"{m // 60:02d}{m % 60:02d}" for m in range(s, e + 1)]


def range_minutes(start_hhmm: str, end_hhmm: str) -> int:
    sh, sm = [int(x) for x in start_hhmm.split(":")]
    eh, em = [int(x) for x in end_hhmm.split(":")]
    return (eh * 60 + em) - (sh * 60 + sm)


def sign_candidates(aspect: str) -> list[int]:
    return [1] if aspect in {"Conjunctio", "Oppositio"} else [1, -1]


def calc_hit(birth: BirthData, points: dict, hit):
    if hit.mode != "Z" or hit.aspect not in ASPECTS:
        return None
    p = canonical_point_name(hit.promissor)
    s = canonical_point_name(hit.significator)
    if p not in points or s not in points:
        return None
    best = None
    for sg in sign_candidates(hit.aspect):
        try:
            if s == "MC" and hit.aspect_side == "promissor":
                c = zodiacal_promissor_aspect_to_mc(birth, p, hit.aspect, sg, points)
            elif hit.aspect_side == "promissor":
                c = zodiacal_promissor_aspect_to_significator(birth, p, hit.aspect, sg, s, points)
            else:
                c = zodiacal_promissor_to_significator_aspect(birth, p, s, hit.aspect, sg, points)
        except Exception:
            continue
        diff = abs(c.arc - float(hit.arc))
        ok = c.direction == hit.direction
        score = (0 if ok else 1, diff)
        if best is None or score < best["score"]:
            best = {"calc": c, "diff": diff, "dir_ok": ok, "sign": sg, "p": p, "s": s, "score": score}
    return best


_MORINUS_COEFF = 365.2422 / 360.0  # Naibod COEFF from Morinus primdirs staticData


def arc_to_date(birth_date: date, arc: float) -> date:
    """Morinus Naibod static-key: convDate(birth)+ti, revConvDate uses 365."""
    ti_years = arc * _MORINUS_COEFF
    birth_dec = birth_date.year + (birth_date - date(birth_date.year, 1, 1)).days / 365.2422
    event_dec = birth_dec + ti_years
    ev_year = int(event_dec)
    frac = event_dec - ev_year
    d_idx = int(frac * 365.0)
    try:
        return date(ev_year, 1, 1) + timedelta(days=d_idx)
    except (ValueError, OverflowError):
        return date(ev_year, 12, 31)


def is_angle_row(row: dict) -> bool:
    return any(a in row["promissor"] or a in row["significator"] for a in ANGLE_POINTS)


def row_signature_penalty(row: dict, event_type: str) -> int:
    rule = EVENT_RULES.get(event_type)
    if not rule:
        return 0
    asp = row["aspect"]
    sig = row["significator"]
    prom = row["promissor"]
    angle_targets = rule.get("angle_targets", set())
    touches_target_angle = sig in angle_targets or prom in angle_targets
    if "good_aspects" in rule:
        return 0 if (asp in rule["good_aspects"] and touches_target_angle) else 1
    if "hard_aspects" in rule:
        return 0 if (asp in rule["hard_aspects"] and touches_target_angle) else 1
    return 0


def main() -> None:
    payload = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    tol_days = int(payload.get("tolerance_days", 62))
    events = []
    for e in payload["events"]:
        s, ed = parse_event_date_window(e["date"])
        events.append(Event(e["id"], s, ed, e["type"], e["text"]))
    min_event_date = min(e.start_date for e in events)
    max_event_date = max(e.end_date for e in events)
    start_hhmm, end_hhmm = payload["subject"]["candidate_range"].split("~")
    span_minutes = range_minutes(start_hhmm, end_hhmm)
    # User rule: 1 hour range => +15 years PD extension.
    pad_years = max(1, math.ceil((span_minutes / 60.0) * 15.0))
    min_bound = min_event_date - timedelta(days=round(365.2422 * pad_years))
    max_bound = max_event_date + timedelta(days=round(365.2422 * pad_years))
    keys = minute_keys(start_hhmm, end_hhmm)

    compare_rows = []
    candidate_rows = []

    for key in keys:
        hhmm = f"{key[:2]}:{key[2:]}:25"
        birth = BirthData.from_strings("1981.10.13", hhmm, "morinus_0345")
        points = expand_antiscia(calculate_natal_points(birth))
        hits = parse_morinus_pd_file(FIXTURE_DIR / f"{key}.txt")
        generated = []
        for h in hits:
            best = calc_hit(birth, points, h)
            if best is None:
                continue
            calc = best["calc"]
            gen_date = arc_to_date(birth.birth_date, calc.arc)
            if gen_date < min_bound or gen_date > max_bound:
                continue
            row = {
                "candidate_time": f"{key[:2]}:{key[2:]}",
                "mode": h.mode,
                "promissor": best["p"],
                "aspect": h.aspect,
                "significator": best["s"],
                "aspect_side": h.aspect_side,
                "engine_direction": calc.direction,
                "engine_arc": round(calc.arc, 6),
                "engine_date": gen_date.isoformat(),
                "orig_direction": h.direction,
                "orig_arc": float(h.arc),
                "orig_date": h.hit_date.isoformat() if h.hit_date else "",
                "arc_diff": round(best["diff"], 6),
                "direction_match": best["dir_ok"],
                "used_sign": best["sign"],
                "is_angle_direction": is_angle_row({"promissor": best["p"], "significator": best["s"]}),
            }
            generated.append(row)
            compare_rows.append(row)

        matched = 0
        required_major_ok = True
        event_details = []
        for e in events:
            planets = TYPE_PLANETS.get(e.event_type, {"Sun", "Jupiter", "Venus", "Mars", "Saturn"})
            pool = [r for r in generated if any(p in r["promissor"] or p in r["significator"] for p in planets)]
            angle_pool = [r for r in pool if r["is_angle_direction"]]
            use_pool = angle_pool if e.event_type in HIGH_PRIORITY_TYPES else (angle_pool or pool)
            best_row = None
            best_key = None
            best_days = None
            for r in use_pool:
                d = day_distance_to_window(datetime.fromisoformat(r["engine_date"]).date(), e.start_date, e.end_date)
                sig_penalty = row_signature_penalty(r, e.event_type)
                rank_key = (d, sig_penalty, r["arc_diff"])
                if best_key is None or rank_key < best_key:
                    best_key = rank_key
                    best_days = d
                    best_row = r
            ok = best_row is not None and best_days is not None and best_days <= tol_days
            if ok:
                matched += 1
            if e.event_type == "surgery_medical_major" and not ok:
                required_major_ok = False
            event_details.append(
                {
                    "candidate_time": f"{key[:2]}:{key[2:]}",
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "event_text": e.text,
                    "event_date": e.start_date.isoformat() if e.start_date == e.end_date else f"{e.start_date.isoformat()}~{e.end_date.isoformat()}",
                    "matched": ok,
                    "abs_days": best_days if best_days is not None else "",
                    "best_pd": f"{best_row['promissor']} {best_row['aspect']} {best_row['significator']}" if best_row else "",
                    "best_pd_date": best_row["engine_date"] if best_row else "",
                    "best_pd_arc": best_row["engine_arc"] if best_row else "",
                    "best_pd_dir": best_row["engine_direction"] if best_row else "",
                }
            )
        mean_days = round(
            sum(d["abs_days"] for d in event_details if isinstance(d["abs_days"], int)) / max(1, sum(1 for d in event_details if isinstance(d["abs_days"], int))),
            3,
        )
        for d in event_details:
            d["matched_events"] = matched
            d["required_major_ok"] = required_major_ok
            d["mean_abs_days_matched"] = mean_days
            candidate_rows.append(d)

    with OUT_COMPARE.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(compare_rows[0].keys()))
        w.writeheader()
        w.writerows(compare_rows)

    with OUT_FULL.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(candidate_rows[0].keys()))
        w.writeheader()
        w.writerows(candidate_rows)

    shortlist = {}
    for r in candidate_rows:
        ct = r["candidate_time"]
        if ct in shortlist:
            continue
        shortlist[ct] = {
            "candidate_time": ct,
            "matched_events": r["matched_events"],
            "required_major_ok": r["required_major_ok"],
            "mean_abs_days_matched": r["mean_abs_days_matched"],
        }
    rows = [v for v in shortlist.values() if v["required_major_ok"]]
    rows.sort(key=lambda x: (-x["matched_events"], x["mean_abs_days_matched"], x["candidate_time"]))
    if not rows:
        rows = list(shortlist.values())
        rows.sort(key=lambda x: (-x["matched_events"], x["mean_abs_days_matched"], x["candidate_time"]))
    with OUT_SHORT.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["candidate_time", "matched_events", "required_major_ok", "mean_abs_days_matched"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(OUT_COMPARE)
    print(OUT_FULL)
    print(OUT_SHORT)
    print(f"event_period={min_event_date.isoformat()}..{max_event_date.isoformat()}")
    print(f"pd_search_period={min_bound.isoformat()}..{max_bound.isoformat()} (pad_years={pad_years})")


if __name__ == "__main__":
    main()
