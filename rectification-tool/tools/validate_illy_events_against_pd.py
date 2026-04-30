from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from rectification_engine.morinus_parser import parse_morinus_pd_file


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "morinus_0325_0405"
EVENTS_PATH = Path(__file__).resolve().parents[1] / "input" / "illy_personal_events.json"
OUT_PATH = Path(__file__).resolve().parents[1] / "output" / "illy_pd_validation_result.json"


TYPE_PLANETS = {
    "university_admission": {"Sun", "Jupiter", "Venus"},
    "employment_start": {"Sun", "Jupiter", "Venus"},
    "career_honor_event": {"Sun", "Jupiter", "Venus"},
    "employment_end": {"Mars", "Saturn"},
    "loss_general": {"Mars", "Saturn"},
    "mental_health_crisis": {"Mars", "Saturn"},
    "surgery_medical_major": {"Mars", "Saturn"},
}
ANGLE_POINTS = {"Asc", "MC", "LoF", "Fortuna"}
HIGH_PRIORITY_TYPES = {
    "university_admission",
    "employment_start",
    "career_honor_event",
    "surgery_medical_major",
    "family_death",
    "marriage",
    "childbirth",
}


@dataclass(frozen=True)
class Event:
    event_id: str
    date_ref: date
    event_type: str
    text: str


def parse_event_date(s: str) -> date:
    s = s.strip()
    if len(s) == 7:
        return datetime.strptime(s + "-15", "%Y-%m-%d").date()
    if len(s) == 10:
        return datetime.strptime(s, "%Y-%m-%d").date()
    raise ValueError(f"Unsupported date format: {s}")


def minute_keys(start_hhmm: str, end_hhmm: str) -> list[str]:
    sh, sm = [int(x) for x in start_hhmm.split(":")]
    eh, em = [int(x) for x in end_hhmm.split(":")]
    s = sh * 60 + sm
    e = eh * 60 + em
    return [f"{m // 60:02d}{m % 60:02d}" for m in range(s, e + 1)]


def hit_has_planet_signature(hit, planets: set[str]) -> bool:
    left = hit.promissor
    right = hit.significator
    return any(p in left or p in right for p in planets)


def hit_is_angle_direction(hit) -> bool:
    left = hit.promissor
    right = hit.significator
    return any(a in left or a in right for a in ANGLE_POINTS)


def main() -> None:
    payload = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    events = [
        Event(
            event_id=e["id"],
            date_ref=parse_event_date(e["date"]),
            event_type=e["type"],
            text=e["text"],
        )
        for e in payload["events"]
    ]
    tol_days = int(payload.get("tolerance_days", 62))
    start_hhmm, end_hhmm = payload["subject"]["candidate_range"].split("~")
    keys = minute_keys(start_hhmm, end_hhmm)

    candidate_results = []
    for key in keys:
        path = FIXTURE_DIR / f"{key}.txt"
        hits = parse_morinus_pd_file(path)
        matched = 0
        details = []
        required_major_ok = True
        for e in events:
            planets = TYPE_PLANETS.get(e.event_type, {"Sun", "Jupiter", "Venus", "Mars", "Saturn"})
            angle_best = None
            minor_best = None
            for h in hits:
                if h.hit_date is None:
                    continue
                if not hit_has_planet_signature(h, planets):
                    continue
                d = abs((h.hit_date - e.date_ref).days)
                candidate = {
                    "abs_days": d,
                    "hit_line": h.raw_line,
                    "hit_date": h.hit_date.isoformat(),
                    "direction": h.direction,
                    "mode": h.mode,
                    "is_angle": hit_is_angle_direction(h),
                }
                if candidate["is_angle"]:
                    if angle_best is None or d < angle_best["abs_days"]:
                        angle_best = candidate
                else:
                    if minor_best is None or d < minor_best["abs_days"]:
                        minor_best = candidate

            # 우선순위 높은 이벤트는 앵글 디렉션만 유효 처리
            if e.event_type in HIGH_PRIORITY_TYPES:
                best = angle_best
            else:
                best = angle_best if angle_best is not None else minor_best

            is_match = best is not None and best["abs_days"] <= tol_days
            if is_match:
                matched += 1
            if e.event_type == "surgery_medical_major" and not is_match:
                required_major_ok = False
            details.append(
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "event_text": e.text,
                    "event_date": e.date_ref.isoformat(),
                    "matched": is_match,
                    "abs_days": best["abs_days"] if best else None,
                    "best_hit": best["hit_line"] if best else None,
                    "used_angle_direction": bool(best and best.get("is_angle")),
                }
            )

        candidate_results.append(
            {
                "candidate_time": f"{key[:2]}:{key[2:]}",
                "matched_events": matched,
                "total_events": len(events),
                "required_major_ok": required_major_ok,
                "details": details,
            }
        )

    candidate_results.sort(
        key=lambda x: (
            not x["required_major_ok"],
            -x["matched_events"],
            x["candidate_time"],
        )
    )

    out = {
        "subject": payload["subject"],
        "tolerance_days": tol_days,
        "top_candidates": candidate_results[:5],
        "all_candidates_summary": [
            {
                "candidate_time": c["candidate_time"],
                "matched_events": c["matched_events"],
                "total_events": c["total_events"],
                "required_major_ok": c["required_major_ok"],
            }
            for c in candidate_results
        ],
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT_PATH)


if __name__ == "__main__":
    main()
