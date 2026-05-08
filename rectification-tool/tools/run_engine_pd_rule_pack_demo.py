from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from rectification_engine.models import BirthData, NatalPoint, Place
from rectification_engine.natal import calculate_natal_points, expand_antiscia, norm360
from rectification_engine.pd_morinus import (
    zodiacal_promissor_aspect_to_mc,
    zodiacal_promissor_aspect_to_significator,
    zodiacal_promissor_to_significator_aspect,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_EVENTS = ROOT / "output" / "engine_rulepack_events.csv"
OUT_HITS = ROOT / "output" / "engine_rulepack_hits.csv"

ASPECTS = ["Conjunctio", "Sextil", "Quadrat", "Trigon", "Oppositio"]
SIGNS = [1, -1]
NAIBOD = 0.9855555556
PLANETS = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
BENEFICS = {"Sun", "Jupiter", "Venus"}
MALEFICS = {"Mars", "Saturn"}
ANGLE_NAMES = {"ASC", "MC", "LoF"}
BASE_PROMISSORS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "LoF", "ASC", "MC"]
SIGNIFICATORS = ["ASC", "MC", "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "LoF"]

MANDATORY_TYPES = {
    "marriage",
    "childbirth",
    "first_employment",
    "university_admission",
    "graduate_school_admission",
}


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    text: str
    y: int
    m: int
    d: int | None


@dataclass(frozen=True)
class Case:
    case_id: str
    birth_date: str
    hhmm: str
    place: Place
    events: list[Event]


def parse_ymd(text: str) -> tuple[int, int, int | None] | None:
    m = re.search(r"(19\d{2}|20\d{2})\D*(\d{1,2})(?:\D*(\d{1,2}))?", text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else None


def split_items(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        for p in re.split(r"[/|,]", line):
            s = p.strip()
            if s:
                out.append(s)
    return out


def month_shift(y: int, m: int, delta: int) -> tuple[int, int]:
    mm = m + delta
    yy = y + (mm - 1) // 12
    mm = ((mm - 1) % 12) + 1
    return yy, mm


def event_window(ev: Event) -> tuple[date, date]:
    if ev.event_type in {"university_admission", "graduate_school_admission"}:
        if ev.m in (1, 2, 3):
            sy, sm = ev.y - 1, 12
            ey, em = ev.y, 5
        else:
            sy, sm = month_shift(ev.y, ev.m, -2)
            ey, em = month_shift(ev.y, ev.m, 2)
    else:
        sy, sm = month_shift(ev.y, ev.m, -2)
        ey, em = month_shift(ev.y, ev.m, 2)
    s = date(sy, sm, 1)
    e = date(ey + 1, 1, 1) - timedelta(days=1) if em == 12 else date(ey, em + 1, 1) - timedelta(days=1)
    return s, e


def arc_to_date(birth_dt: datetime, arc: float) -> date:
    days = (arc / NAIBOD) * 365.2422 - 2.15
    return (birth_dt + timedelta(days=days)).date()


def allowed_promissors(points: dict[str, NatalPoint]) -> list[str]:
    names: list[str] = []
    for p in BASE_PROMISSORS:
        if p in points:
            names.append(p)
            for pref in ("Antiscion ", "Contraantiscion "):
                n = pref + p
                if n in points:
                    names.append(n)
    return names


def parse_lr_signature(promissor: str, significator: str) -> tuple[bool, bool, bool, bool]:
    p_is_angle = any(a in promissor for a in ANGLE_NAMES)
    s_is_angle = any(a in significator for a in ANGLE_NAMES)
    p_planet = any(p in promissor for p in PLANETS)
    s_planet = any(p in significator for p in PLANETS)
    return p_is_angle, s_is_angle, p_planet, s_planet


def is_planet_angle_or_angle_planet(promissor: str, significator: str) -> bool:
    p_is_angle, s_is_angle, p_planet, s_planet = parse_lr_signature(promissor, significator)
    return (p_planet and s_is_angle and not p_is_angle and not s_planet) or (
        s_planet and p_is_angle and not s_is_angle and not p_planet
    )


def event_allowed_planets(event_type: str) -> set[str]:
    if event_type in {
        "university_admission",
        "graduate_school_admission",
        "employment_start",
        "first_employment",
        "promotion_award",
        "career_honor_event",
        "graduation",
        "marriage",
        "childbirth",
    }:
        return BENEFICS
    if event_type in {"employment_end", "dropout", "family_death", "surgery_medical_major", "mental_health_crisis"}:
        return MALEFICS
    return BENEFICS | MALEFICS


def line_has_allowed_planet(promissor: str, significator: str, allowed: set[str]) -> bool:
    return any(p in promissor or p in significator for p in allowed)


def build_cases() -> list[Case]:
    seoul = Place("Seoul", 37.5665, 126.9780, "Asia/Seoul")
    yongin = Place("Yongin", 37.2411, 127.1776, "Asia/Seoul")

    g409 = "1995년 3월 대학입학, 2000년 9월 대학원 입학, 2005년 9월 중국 박사과정 입학, 2012년 6월 박사학위 취득, 2011년 5월 대학교 비정년 전임강사 첫 시작, 2021년 3월 대학교 비정년 조교수 임용, 2023년 9월 국립대학교 정년 조교수 임용"
    h409 = "1997년 7월 연애, 2003년 10월 결혼, 2006년 4월 장남 출생, 2009년 6월 차남 출생"
    e409: list[Event] = []
    i = 1
    for t in split_items(g409):
        ymd = parse_ymd(t)
        if not ymd:
            continue
        et = "career_honor_event"
        if "대학원 입학" in t:
            et = "graduate_school_admission"
        elif ("대학입학" in t) or ("박사과정 입학" in t):
            et = "university_admission"
        elif ("임용" in t) or ("시작" in t):
            et = "first_employment" if "첫 시작" in t else "employment_start"
        elif "취득" in t:
            et = "promotion_award"
        e409.append(Event(f"G{i:02d}", et, t, *ymd))
        i += 1
    for t in split_items(h409):
        ymd = parse_ymd(t)
        if not ymd:
            continue
        if "결혼" in t:
            e409.append(Event("H_MARRIAGE", "marriage", t, *ymd))
        if any(k in t for k in ("출생", "출산", "장남", "차남")):
            e409.append(Event("H_BIRTH", "childbirth", t, *ymd))

    g408 = "2011 대학입학/2017년8월 대학졸업/2017년 9월 런던 대학원 입학/ 2018년 10월 런던 대학원 학기끝/주식회사 와이오오아키텍스튜디오 | 2025.04.02 ~/와이오오 | 2024.07.22 ~ 2025.04.02/(주)라이터 | 2022.03.01 ~ 2022.12.10/주식회사 로컬스티치 | 2021.03.01 ~ 2021.10.30/이케아코리아유한회사 | 2019.04.01 ~ 2021.01.01"
    h408 = "2026년 2월 24일부터 사귄거로 보면됨"
    e408: list[Event] = []
    i = 1
    for t in split_items(g408):
        ymd = parse_ymd(t)
        if not ymd:
            continue
        et = "career_honor_event"
        if "대학원 입학" in t:
            et = "graduate_school_admission"
        elif "대학입학" in t:
            et = "university_admission"
        elif ("대학졸업" in t) or ("학기끝" in t):
            et = "graduation"
        e408.append(Event(f"G{i:02d}", et, t, *ymd))
        i += 1
    for t in split_items(h408):
        ymd = parse_ymd(t)
        if ymd:
            e408.append(Event("H_REL", "relationship", t, *ymd))

    return [
        Case("kim_2049", "1976.1.22", "20:49", seoul, e409),
        Case("yoo_1548", "1992.8.12", "15:48", yongin, e408),
    ]


def main() -> None:
    event_rows = []
    hit_rows = []

    for case in build_cases():
        y, m, d = [int(x) for x in case.birth_date.replace(".", "-").split("-")]
        hh, mm = [int(x) for x in case.hhmm.split(":")]
        birth = BirthData(date(y, m, d), time(hh, mm, 0), case.place)
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

        strong_benefic_anchors = [
            g
            for g in generated
            if is_planet_angle_or_angle_planet(g[0], g[2])
            and any(p in g[0] or p in g[2] for p in BENEFICS)
            and g[1] in {"Conjunctio", "Oppositio"}
            and ("ASC" in g[0] or "ASC" in g[2])
        ]
        strong_benefic_anchors.sort(key=lambda x: x[5])

        for ev in case.events:
            ws, we = event_window(ev)
            allowed = event_allowed_planets(ev.event_type)
            hits = [
                g
                for g in generated
                if is_planet_angle_or_angle_planet(g[0], g[2])
                and line_has_allowed_planet(g[0], g[2], allowed)
                and ws <= g[5] <= we
            ]
            hits.sort(key=lambda x: (x[5], abs(x[4])))

            # 흐름형 유효성: 강한 길성 앵글 히트가 사건시점 전후를 감싸는 경우
            center = date(ev.y, ev.m, ev.d or 15)
            prev = [a for a in strong_benefic_anchors if a[5] <= center]
            nxt = [a for a in strong_benefic_anchors if a[5] >= center]
            flow_bridged = bool(prev and nxt and (nxt[0][5] - prev[-1][5]).days <= 420)

            event_rows.append(
                {
                    "case_id": case.case_id,
                    "event_id": ev.event_id,
                    "event_type": ev.event_type,
                    "event_text": ev.text,
                    "window": f"{ws}~{we}",
                    "hit_count": len(hits),
                    "mandatory": ev.event_type in MANDATORY_TYPES,
                    "flow_bridged": flow_bridged,
                }
            )
            for idx, h in enumerate(hits[:12], 1):
                hit_rows.append(
                    {
                        "case_id": case.case_id,
                        "event_id": ev.event_id,
                        "rank_in_event": idx,
                        "promissor": h[0],
                        "aspect": h[1],
                        "significator": h[2],
                        "direction": h[3],
                        "arc": round(h[4], 6),
                        "pd_date": h[5].isoformat(),
                    }
                )

    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_EVENTS.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(event_rows[0].keys()))
        w.writeheader()
        w.writerows(event_rows)
    with OUT_HITS.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(hit_rows[0].keys()))
        w.writeheader()
        w.writerows(hit_rows)

    print(OUT_EVENTS)
    print(OUT_HITS)


if __name__ == "__main__":
    main()

