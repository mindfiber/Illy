from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from rectification_engine.models import BirthData, NatalPoint
from rectification_engine.natal import calculate_natal_points, expand_antiscia, norm360
from rectification_engine.pd_morinus import (
    zodiacal_promissor_aspect_to_mc,
    zodiacal_promissor_aspect_to_significator,
    zodiacal_promissor_to_significator_aspect,
)

ROOT = Path(__file__).resolve().parents[1]
IN_CSV = ROOT / "input" / "intake_responses.csv"
OUT_TOP = ROOT / "output" / "yuhajin_408_top.csv"
OUT_AUDIT = ROOT / "output" / "yuhajin_408_audit.csv"

ASPECTS = ["Conjunctio", "Sextil", "Quadrat", "Trigon", "Oppositio"]
SIGNS = [1, -1]
NAIBOD = 0.9855555556
BASE_PROMISSORS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "LoF", "ASC", "MC"]
SIGNIFICATORS = ["ASC", "MC", "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "LoF"]
ANGLE_NAMES = {"ASC", "MC", "LoF", "DSC"}


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    text: str
    start_date: date
    end_date: date


def parse_window(text: str) -> tuple[date, date] | None:
    m = re.search(r"(19\d{2}|20\d{2})\D*(\d{1,2})(?:\D*(\d{1,2}))?", text)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    d = m.group(3)
    if d:
        dd = date(y, mo, int(d))
        return dd, dd
    s = date(y, mo, 1)
    e = date(y + 1, 1, 1) - timedelta(days=1) if mo == 12 else date(y, mo + 1, 1) - timedelta(days=1)
    return s, e


def split_items(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        for p in re.split(r"[,/]", line):
            s = p.strip()
            if s:
                out.append(s)
    return out


def build_events(row: list[str]) -> list[Event]:
    events: list[Event] = []
    i = 1
    hb = 1
    for t in split_items(row[6]):
        w = parse_window(t)
        if not w:
            continue
        et = "career_honor_event"
        if ("대학입학" in t) or ("대학진학" in t) or ("대학원 입학" in t):
            et = "university_admission"
        elif ("임용" in t) or ("취업" in t) or ("시작" in t):
            et = "employment_start"
        elif "퇴사" in t:
            et = "employment_end"
        elif "승진" in t:
            et = "promotion_award"
        events.append(Event(f"G{i:02d}", et, t, w[0], w[1]))
        i += 1
    for t in split_items(row[7]):
        w = parse_window(t)
        if not w:
            continue
        if "결혼" in t:
            events.append(Event("H_MARRIAGE", "marriage", t, w[0], w[1]))
        if ("출생" in t) or ("출산" in t) or ("득남" in t):
            events.append(Event(f"H_BIRTH_{hb:02d}", "childbirth", t, w[0], w[1]))
            hb += 1
    return events


def day_distance(target: date, start: date, end: date) -> int:
    if target < start:
        return (start - target).days
    if target > end:
        return (target - end).days
    return 0


def arc_to_date(birth_dt: datetime, arc: float) -> date:
    days = (arc / NAIBOD) * 365.2422 - 2.15
    return (birth_dt + timedelta(days=days)).date()


def event_planets(event_type: str, is_female: bool) -> set[str]:
    if event_type == "marriage":
        return {"Jupiter", "Sun", "Venus"} if is_female else {"Jupiter", "Venus", "Sun"}
    if event_type == "childbirth":
        return {"Jupiter", "Sun", "Venus"}
    if event_type in {"university_admission", "employment_start", "promotion_award", "career_honor_event"}:
        return {"Sun", "Jupiter", "Venus"}
    return {"Mars", "Saturn", "Moon"}


def event_weight(event_type: str) -> int:
    if event_type == "marriage":
        return 5
    if event_type == "childbirth":
        return 4
    if event_type in {"university_admission", "employment_start", "promotion_award", "career_honor_event"}:
        return 3
    return 1


def allowed_promissors(points: dict[str, NatalPoint]) -> list[str]:
    names = []
    for p in BASE_PROMISSORS:
        if p in points:
            names.append(p)
            for pref in ("Antiscion ", "Contraantiscion "):
                n = pref + p
                if n in points:
                    names.append(n)
    return names


def main() -> None:
    rows = list(csv.reader(open(IN_CSV, encoding="utf-8-sig", newline="")))
    row = rows[407]  # 408행
    events = build_events(row)
    is_female = row[3].strip() == "여"

    score_rows = []
    audit_rows = []
    for m in range(15 * 60 + 45, 16 * 60 + 15 + 1):
        hh, mm = m // 60, m % 60
        birth = BirthData.from_strings("1992.8.12", f"{hh:02d}:{mm:02d}:00", "seoul")
        birth_dt = datetime.combine(birth.birth_date, birth.birth_time)
        points = expand_antiscia(calculate_natal_points(birth)).copy()
        points["DSC"] = NatalPoint("DSC", norm360(points["ASC"].longitude + 180.0), point_type="angle")
        generated = []
        for p in allowed_promissors(points):
            for s in SIGNIFICATORS:
                if s not in points:
                    continue
                for asp in ASPECTS:
                    signs = [1] if asp in {"Conjunctio", "Oppositio"} else SIGNS
                    for sg in signs:
                        try:
                            c = zodiacal_promissor_aspect_to_significator(birth, p, asp, sg, s, points)
                            generated.append((p, asp, s, c.direction, c.arc, arc_to_date(birth_dt, c.arc)))
                        except Exception:
                            pass
                        try:
                            c = zodiacal_promissor_to_significator_aspect(birth, p, s, asp, sg, points)
                            generated.append((p, asp, s, c.direction, c.arc, arc_to_date(birth_dt, c.arc)))
                        except Exception:
                            pass
            for asp in ASPECTS:
                signs = [1] if asp in {"Conjunctio", "Oppositio"} else SIGNS
                for sg in signs:
                    try:
                        c = zodiacal_promissor_aspect_to_mc(birth, p, asp, sg, points)
                        generated.append((p, asp, "MC", c.direction, c.arc, arc_to_date(birth_dt, c.arc)))
                    except Exception:
                        pass
        dedup = {}
        for g in generated:
            k = (g[0], g[1], g[2], g[3], g[5].isoformat())
            if k not in dedup or g[4] < dedup[k][4]:
                dedup[k] = g
        generated = list(dedup.values())

        matched_count = 0
        weighted_total = 0
        weighted_matched = 0
        high_total = 0
        high_matched = 0
        g_total = sum(1 for e in events if e.event_id.startswith("G"))
        g_miss = 0
        marriage_ok = False
        matched_types: list[str] = []
        for ev in events:
            w = event_weight(ev.event_type)
            weighted_total += w
            if w >= 3:
                high_total += w
            pool = [
                x
                for x in generated
                if (x[0] in ANGLE_NAMES or x[2] in ANGLE_NAMES)
                and any(pp in x[0] or pp in x[2] for pp in event_planets(ev.event_type, is_female))
            ]
            best = None
            for x in pool:
                d = day_distance(x[5], ev.start_date, ev.end_date)
                rk = (d, abs(x[4]))
                if best is None or rk < best[0]:
                    best = (rk, x, d)
            ok = best is not None and best[2] <= 62
            if ok:
                matched_count += 1
                weighted_matched += w
                if w >= 3:
                    high_matched += w
                matched_types.append(f"{ev.event_id}:{ev.event_type}")
            if ev.event_id.startswith("G") and not ok:
                g_miss += 1
            if ev.event_id == "H_MARRIAGE" and ok:
                marriage_ok = True
            audit_rows.append(
                {
                    "candidate_time": f"{hh:02d}:{mm:02d}",
                    "event_id": ev.event_id,
                    "event_type": ev.event_type,
                    "matched": ok,
                    "promissor": best[1][0] if best else "",
                    "aspect": best[1][1] if best else "",
                    "significator": best[1][2] if best else "",
                    "direction": best[1][3] if best else "",
                    "pd_date": best[1][5].isoformat() if best else "",
                    "abs_days": best[2] if best else "",
                }
            )
        eligible = g_miss <= 2 and marriage_ok
        score_rows.append(
            {
                "candidate_time": f"{hh:02d}:{mm:02d}",
                "matched_count": matched_count,
                "high_match_rate": round(high_matched / high_total, 6) if high_total else 0.0,
                "weighted_match_rate": round(weighted_matched / weighted_total, 6) if weighted_total else 0.0,
                "g_total": g_total,
                "g_miss": g_miss,
                "marriage_ok": marriage_ok,
                "eligible": eligible,
                "matched_types": "|".join(matched_types),
            }
        )

    score_rows.sort(
        key=lambda x: (
            not x["eligible"],
            -x["high_match_rate"],
            -x["weighted_match_rate"],
            -x["matched_count"],
            x["g_miss"],
            x["candidate_time"],
        )
    )

    OUT_TOP.parent.mkdir(parents=True, exist_ok=True)
    with OUT_TOP.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(score_rows[0].keys()))
        w.writeheader()
        w.writerows(score_rows)
    with OUT_AUDIT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(audit_rows[0].keys()))
        w.writeheader()
        w.writerows(audit_rows)
    print(OUT_TOP)
    print(OUT_AUDIT)
    for i, r in enumerate(score_rows[:3], 1):
        print(i, r)


if __name__ == "__main__":
    main()

