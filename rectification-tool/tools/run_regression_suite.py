from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from rectification_engine.models import BirthData, NatalPoint, Place
from rectification_engine.morinus_parser import parse_morinus_pd_file
from rectification_engine.natal import calculate_natal_points, expand_antiscia, norm360
from rectification_engine.pd_morinus import (
    canonical_point_name,
    zodiacal_promissor_aspect_to_angle,
    zodiacal_promissor_aspect_to_significator,
    zodiacal_promissor_to_significator_aspect,
)

ROOT = Path(__file__).resolve().parents[1]
IN_DEFAULT = ROOT / "input" / "regression_cases.json"
OUT_DIR = ROOT / "output"
_MORINUS_COEFF = 365.2422 / 360.0  # Naibod static key: ti(years) = arc * COEFF
ASPECTS = ["Conjunctio", "Sextil", "Quadrat", "Trigon", "Oppositio"]
SIGNS = [1, -1]
PLANETS = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
BENEFICS = {"Sun", "Jupiter", "Venus"}
MALEFICS = {"Mars", "Saturn"}
ANGLE = {"ASC", "MC", "LoF"}
PROM = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "LoF", "ASC", "MC"]
SIG = ["ASC", "MC", "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "LoF"]
MAND = {"marriage", "childbirth", "first_employment", "university_admission", "graduate_school_admission"}


@dataclass
class Ev:
    id: str
    et: str
    txt: str
    y: int
    m: int
    d: int | None = None
    precision: str = "month"


def msh(y: int, m: int, d: int) -> tuple[int, int]:
    mm = m + d
    yy = y + (mm - 1) // 12
    mm = ((mm - 1) % 12) + 1
    return yy, mm


def win(e: Ev) -> tuple[date, date]:
    if e.precision == "year":
        return date(e.y, 1, 1), date(e.y, 12, 31)
    if e.et in {"university_admission", "graduate_school_admission"}:
        if e.m in (1, 2, 3):
            # IMMUTABLE_RULES #15: 11월-3월 hit가 1순위, 4월 2순위, 5월 3순위
            sy, sm = e.y - 1, 11
            ey, em = e.y, 5
        else:
            sy, sm = msh(e.y, e.m, -2)
            ey, em = msh(e.y, e.m, 2)
    else:
        sy, sm = msh(e.y, e.m, -2)
        ey, em = msh(e.y, e.m, 2)
    s = date(sy, sm, 1)
    eom = date(ey + 1, 1, 1) - timedelta(days=1) if em == 12 else date(ey, em + 1, 1) - timedelta(days=1)
    return s, eom


def admission_month_tier(ev: Ev, pd_date: date) -> int:
    if ev.et != "university_admission":
        return 0
    m = pd_date.month
    if m in (11, 12, 1, 2, 3):
        return 0
    if m == 4:
        return 1
    if m == 5:
        return 2
    return 3


def arc_date(birth_date: date, arc: float) -> date:
    """Morinus Naibod static-key date formula: convDate(birth)+ti, revConvDate uses 365."""
    ti_years = arc * _MORINUS_COEFF
    birth_dec = birth_date.year + ((birth_date - date(birth_date.year, 1, 1)).days) / 365.2422
    event_dec = birth_dec + ti_years
    ev_year = int(event_dec)
    frac = event_dec - ev_year
    d_idx = int(frac * 365.0)
    try:
        return date(ev_year, 1, 1) + timedelta(days=d_idx)
    except (ValueError, OverflowError):
        return date(ev_year, 12, 31)


def allowed(et: str) -> set[str]:
    if et in {"university_admission", "graduate_school_admission", "employment_start", "first_employment", "promotion_award", "career_honor_event", "graduation", "marriage", "childbirth", "relationship"}:
        return BENEFICS
    if et in {"employment_end", "dropout", "family_death", "surgery_medical_major", "mental_health_crisis"}:
        return MALEFICS
    return BENEFICS | MALEFICS


# G_GENERAL: 길성 일반 이벤트 (admission, employment_start, etc.)
G_GENERAL = {
    "university_admission", "graduate_school_admission",
    "employment_start", "first_employment",
    "promotion_award", "career_honor_event", "graduation",
}

# K_HARSH: 흉성 이벤트 (수술, 사망, 상실 등)
K_HARSH = {
    "surgery_medical_major", "mental_health_crisis",
    "family_death", "loss_general",
    "employment_end", "dropout",
}


# NOTE: day-precision bonus 룰은 사용자가 명시적으로 거부함.
# 임상상 정확한 날짜까지 기록되는 경우가 드물어, ±N일 차등 가산점은 부적절.


def pa_ap(p: str, s: str) -> bool:
    """Major direction: planet-angle, angle-planet, planet-LoF, LoF-planet."""
    pA = any(a in p for a in ANGLE)
    sA = any(a in s for a in ANGLE)
    pP = any(x in p for x in PLANETS)
    sP = any(x in s for x in PLANETS)
    return (pP and sA and not pA and not sP) or (sP and pA and not sA and not pP)


def involves_moon(p: str, s: str) -> bool:
    return "Moon" in p or "Moon" in s


def aspect_quality(p: str, s: str) -> str:
    """Quality of a planet-planet PD relationship for minor classification.
    Returns one of: benefic_benefic, malefic_malefic, benefic_malefic, mixed.
    """
    p_b = any(x in p for x in BENEFICS)
    p_m = any(x in p for x in MALEFICS)
    s_b = any(x in s for x in BENEFICS)
    s_m = any(x in s for x in MALEFICS)
    if p_b and s_b:
        return "benefic_benefic"
    if p_m and s_m:
        return "malefic_malefic"
    if (p_b and s_m) or (p_m and s_b):
        return "benefic_malefic"
    return "mixed"


# H_MARRIAGE_BIRTH: 결혼/출산 (룰 13, 14: Sun/Jupiter/Venus 중심)
H_MARRIAGE_BIRTH = {"marriage", "childbirth"}
# H_RELATIONSHIP: 연애 (Venus 메이저만, 다른 길성은 Minor·Equal)
H_RELATIONSHIP = {"relationship"}
# CRITICAL_HARSH: 중요 흉성 (Major만 인정, 마이너 안 됨)
CRITICAL_HARSH = {"family_death"}


def has_venus(p: str, s: str) -> bool:
    return "Venus" in p or "Venus" in s


def classify_match(ev_type: str, hits_major: list, hits_minor: list) -> tuple[str, list, float]:
    """Apply event-category matching rules. Returns (kind, picked_hits, weight_factor).
    kind: "" (no match), "Major", "Minor·Single", "Minor·Cluster", "Minor·Equal"
    """
    # G_GENERAL + 결혼/출산: Sun/Jupiter/Venus Major 인정. 마이너 길성↔길성 1개 또는 군집 3+.
    if ev_type in G_GENERAL or ev_type in H_MARRIAGE_BIRTH:
        if hits_major:
            return "Major", hits_major, 1.0
        bb = [h for h in hits_minor if aspect_quality(h[0], h[2]) == "benefic_benefic"]
        if bb:
            return "Minor·Single", bb, 0.7
        if len(hits_minor) >= 3:
            return "Minor·Cluster", hits_minor, 0.7
        return "", [], 0.0

    # H_RELATIONSHIP (연애): Venus 메이저만 진짜 메이저. 다른 길성 메이저나 마이너는 Minor·Equal (1.0).
    if ev_type in H_RELATIONSHIP:
        venus_major = [h for h in hits_major if has_venus(h[0], h[2])]
        if venus_major:
            return "Major", venus_major, 1.0
        if hits_major:
            return "Minor·Equal", hits_major, 1.0
        equal = [h for h in hits_minor if aspect_quality(h[0], h[2]) in ("benefic_benefic", "benefic_malefic")]
        if equal:
            return "Minor·Equal", equal, 1.0
        if len(hits_minor) >= 3:
            return "Minor·Cluster", hits_minor, 0.7
        return "", [], 0.0

    # K_HARSH: Mars/Saturn 메이저. 중요 흉성(CRITICAL_HARSH)은 메이저만. 일반은 마이너 Equal/Cluster 인정.
    if ev_type in K_HARSH:
        if hits_major:
            return "Major", hits_major, 1.0
        if ev_type in CRITICAL_HARSH:
            return "", [], 0.0
        equal = [h for h in hits_minor if aspect_quality(h[0], h[2]) in ("malefic_malefic", "benefic_malefic")]
        if equal:
            return "Minor·Equal", equal, 1.0
        if len(hits_minor) >= 3:
            return "Minor·Cluster", hits_minor, 0.7
        return "", [], 0.0

    # 기타: Major만
    if hits_major:
        return "Major", hits_major, 1.0
    return "", [], 0.0


def promissor_can_cast_aspect(p: str) -> bool:
    return not any(a in p for a in ANGLE)


def significator_can_receive_aspected(s: str) -> bool:
    return not any(a in s for a in ANGLE)


def parse_range_days(text: str) -> int | None:
    import re
    nums = re.findall(r"(19\d{2}|20\d{2})\D*(\d{1,2})\D*(\d{1,2})", text or "")
    if len(nums) < 2:
        return None
    try:
        y1, m1, d1 = [int(x) for x in nums[0]]
        y2, m2, d2 = [int(x) for x in nums[1]]
        s = date(y1, m1, d1)
        e = date(y2, m2, d2)
    except ValueError:
        return None
    if e < s:
        return None
    return (e - s).days


def is_career_event(ev: Ev) -> bool:
    return ev.et in {"career_honor_event", "employment_start", "first_employment"}


def career_weight(ev: Ev) -> float:
    if not is_career_event(ev):
        return 1.0
    days = parse_range_days(ev.txt)
    if days is None:
        return 1.0
    if days >= 365:
        return 1.0
    if days >= 180:
        return 0.6
    return 0.3


def is_founding_event(ev: Ev) -> bool:
    t = (ev.txt or "").lower()
    return any(k in t for k in ("창업", "창립", "founded", "founding"))


def event_base_weight(ev: Ev) -> float:
    # 사용자 규칙: 장기 지속된 창업 이벤트를 일반 취업 이벤트보다 우선
    if is_founding_event(ev):
        return 4.0
    if ev.et in {"university_admission", "graduate_school_admission"}:
        return 3.0
    if ev.et == "graduation":
        return 0.5
    if ev.et in MAND:
        return 2.0
    return 1.0


def normalize_point_name(name: str) -> str:
    return canonical_point_name(name)


def signature_key(p: str, a: str, s: str, d: str) -> tuple[str, str, str, str]:
    return (normalize_point_name(p), a, normalize_point_name(s), d)


def full_key(p: str, a: str, s: str, d: str, dt: date) -> tuple[str, str, str, str, str]:
    return (normalize_point_name(p), a, normalize_point_name(s), d, dt.isoformat())


def generate_pd_hits(b: BirthData) -> list[tuple[str, str, str, str, float, date]]:
    pts = expand_antiscia(calculate_natal_points(b)).copy()
    pts["DSC"] = NatalPoint("DSC", norm360(pts["ASC"].longitude + 180), point_type="angle")
    ps: list[str] = []
    for p in PROM:
        if p in pts:
            ps.append(p)
            for pref in ("Antiscion ", "Contraantiscion "):
                if pref + p in pts:
                    ps.append(pref + p)
    gen = []
    for p in ps:
        for s in SIG:
            if s not in pts:
                continue
            for a in ASPECTS:
                signs = [1] if a in ("Conjunctio", "Oppositio") else SIGNS
                for sg in signs:
                    if promissor_can_cast_aspect(p):
                        try:
                            c = zodiacal_promissor_aspect_to_significator(b, p, a, sg, s, pts)
                            gen.append((p, a, s, c.direction, c.arc, arc_date(b.birth_date, c.arc)))
                        except Exception:
                            pass
                    if significator_can_receive_aspected(s):
                        try:
                            c = zodiacal_promissor_to_significator_aspect(b, p, s, a, sg, pts)
                            gen.append((p, a, s, c.direction, c.arc, arc_date(b.birth_date, c.arc)))
                        except Exception:
                            pass
        for a in ASPECTS:
            signs = [1] if a in ("Conjunctio", "Oppositio") else SIGNS
            for sg in signs:
                for angle in ("ASC", "MC"):
                    try:
                        c = zodiacal_promissor_aspect_to_angle(b, p, a, sg, angle, pts)
                        gen.append((p, a, angle, c.direction, c.arc, arc_date(b.birth_date, c.arc)))
                    except Exception:
                        pass
    dmap: dict[tuple[str, str, str, str, str], tuple[str, str, str, str, float, date]] = {}
    for g in gen:
        k = (g[0], g[1], g[2], g[3], g[5].isoformat())
        if k not in dmap or g[4] < dmap[k][4]:
            dmap[k] = g
    return list(dmap.values())


def parse_events(raw_events: list[dict[str, Any]]) -> list[Ev]:
    out: list[Ev] = []
    for r in raw_events:
        precision = str(r.get("date_precision", "month"))
        month = int(r.get("month", 6))
        out.append(Ev(r["id"], r["event_type"], r.get("text", ""), int(r["year"]), month, r.get("day"), precision))
    return out


def eval_case(case: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    y, m, d = [int(x) for x in case["birth_date"].split("-")]
    place = Place(case["place"]["name"], float(case["place"]["lat"]), float(case["place"]["lon"]), case["place"]["tz"])
    start_h, start_m = [int(x) for x in case["range_start"].split(":")]
    end_h, end_m = [int(x) for x in case["range_end"].split(":")]
    sM = start_h * 60 + start_m
    eM = end_h * 60 + end_m
    events = parse_events(case["events"])
    birth_second = int(case.get("birth_second", 0))

    score_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    # 1순위 범위 (priority window) 계산 — IMMUTABLE_RULES #18
    # 단일 시간 입력 → ±15분, range 입력 → range 양 끝 ±10분.
    # input data에 input_form 명시 안 되어 있으면 expected_time 기준 ±15분 단일.
    expected_time = case.get("expected_time", "")
    pri_start_min = None
    pri_end_min = None
    input_form = case.get("input_form")  # "single" or "range" or None
    if input_form == "range" and case.get("input_range_start") and case.get("input_range_end"):
        rs_h, rs_m = [int(x) for x in case["input_range_start"].split(":")]
        re_h, re_m = [int(x) for x in case["input_range_end"].split(":")]
        pri_start_min = rs_h * 60 + rs_m - 10
        pri_end_min = re_h * 60 + re_m + 10
    elif expected_time:
        eh, em = [int(x) for x in expected_time.split(":")]
        em_total = eh * 60 + em
        pri_start_min = em_total - 15
        pri_end_min = em_total + 15

    # Per-candidate state: store both Major-only and Major+Minor matching results
    candidates: list[dict[str, Any]] = []

    for mm in range(sM, eM + 1):
        hh, mi = mm // 60, mm % 60
        hhmm = f"{hh:02d}:{mi:02d}"
        b = BirthData(date(y, m, d), time(hh, mi, birth_second), place)
        gen = generate_pd_hits(b)
        per_event: list[dict[str, Any]] = []
        for ev in events:
            ws, we = win(ev)
            aset = allowed(ev.et)
            in_window = [g for g in gen if ws <= g[5] <= we]
            relevant = [g for g in in_window if any(p in g[0] or p in g[2] for p in aset)]
            hits_major = [g for g in relevant if pa_ap(g[0], g[2]) and not involves_moon(g[0], g[2])]
            hits_minor = [g for g in relevant if not pa_ap(g[0], g[2])]
            sort_key = lambda x: (admission_month_tier(ev, x[5]), x[5], abs(x[4]))
            hits_major.sort(key=sort_key)
            hits_minor.sort(key=sort_key)
            kind, picked_pool, weight_factor = classify_match(ev.et, hits_major, hits_minor)
            per_event.append({
                "ev": ev,
                "kind": kind,
                "picked": picked_pool[:3],
                "weight_factor": weight_factor,
                "hits_major": hits_major,
                "hits_minor": hits_minor,
            })
        candidates.append({
            "time": hhmm,
            "per_event": per_event,
        })

    # Case-level mandatory determination
    # Major-strict: mandatory ok requires every mandatory event to have a Major match.
    # Fallback: if NO candidate satisfies major-strict, allow Minor matches to count
    # for mandatory_ok (e.g. illy chart with minor-heavy early period).
    def has_major_for_event(per_event_entry) -> bool:
        ev = per_event_entry["ev"]
        if ev.et not in MAND:
            return True  # not mandatory, doesn't gate
        return bool(per_event_entry["hits_major"])

    def mandatory_ok_strict(cand) -> bool:
        return all(has_major_for_event(pe) for pe in cand["per_event"])

    def mandatory_ok_any(cand) -> bool:
        # Any kind of match (Major / Minor·Single / Minor·Cluster) for each mandatory event
        for pe in cand["per_event"]:
            if pe["ev"].et in MAND and not pe["picked"]:
                return False
        return True

    any_strict_ok = any(mandatory_ok_strict(c) for c in candidates)

    # Now build score_rows with case-level fallback applied
    for cand in candidates:
        hhmm = cand["time"]
        matched = [(pe["ev"], pe["picked"], pe["kind"], pe["weight_factor"])
                   for pe in cand["per_event"] if pe["picked"]]
        score = 0.0
        major_count = 0
        uni_tiers: list[int] = []
        for ev, hs, kind, weight_factor in matched:
            base = event_base_weight(ev)
            base -= 0.5 * admission_month_tier(ev, hs[0][5])
            base *= career_weight(ev)
            score += base * weight_factor
            if kind in ("Major", "Minor·Equal"):
                major_count += 1
            if ev.et == "university_admission":
                uni_tiers.append(admission_month_tier(ev, hs[0][5]))
        score += sum(0.25 * len(hs) for _, hs, _, _ in matched)
        max_uni_tier = max(uni_tiers) if uni_tiers else 9
        min_uni_tier = min(uni_tiers) if uni_tiers else 9

        if any_strict_ok:
            mand_ok_final = mandatory_ok_strict(cand)
        else:
            mand_ok_final = mandatory_ok_any(cand)

        # Audit rows
        for pe in cand["per_event"]:
            for h in pe["picked"]:
                audit_rows.append({
                    "case_id": case["case_id"],
                    "time": hhmm,
                    "event_id": pe["ev"].id,
                    "event_type": pe["ev"].et,
                    "match_kind": pe["kind"],
                    "promissor": normalize_point_name(h[0]),
                    "aspect": h[1],
                    "significator": normalize_point_name(h[2]),
                    "direction": h[3],
                    "engine_arc": round(float(h[4]), 6),
                    "pd_date": h[5].isoformat(),
                })
        # 1순위 범위 안인지 (IMMUTABLE_RULES #18)
        cand_min = int(hhmm.split(":")[0]) * 60 + int(hhmm.split(":")[1])
        if pri_start_min is not None and pri_end_min is not None:
            in_priority = pri_start_min <= cand_min <= pri_end_min
        else:
            in_priority = True  # 1순위 범위 정보 없으면 모든 후보 동등

        score_rows.append({
            "case_id": case["case_id"],
            "time": hhmm,
            "score": round(score, 4),
            "major_count": major_count,
            "matched_count": len(matched),
            "mandatory_ok": mand_ok_final,
            "in_priority": in_priority,
            "min_uni_tier": min_uni_tier,
            "max_uni_tier": max_uni_tier,
            "fallback_minor": not any_strict_ok,
        })

    # 정렬 키 (IMMUTABLE_RULES + 사용자 추가 룰):
    # 1) mandatory_ok (메이저 우선 + case-level fallback)
    # 2) 1순위 범위 안 (#18: 사용자 입력 기반 priority window)
    # 3) 대학입학 month tier
    # 4) matched_count (매칭 다양성 우선)
    # 5) major_count (메이저 매칭 비중)
    # 6) score
    score_rows.sort(key=lambda x: (
        not x["mandatory_ok"],
        not x["in_priority"],
        x["max_uni_tier"],
        x["min_uni_tier"],
        -x["matched_count"],
        -x["major_count"],
        -x["score"],
        x["time"],
    ))
    return score_rows, audit_rows


def strict_rank_with_morinus(case: dict[str, Any], scored: list[dict[str, Any]], audits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = parse_events(case["events"])
    mandatory_ids = {e.id for e in events if e.et in MAND}
    by_time_event: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for a in audits:
        by_time_event.setdefault((a["time"], a["event_id"]), []).append(a)

    strict_rows: list[dict[str, Any]] = []
    for row in scored:
        t = row["time"]
        fpath = case.get("morinus_files", {}).get(t)
        if not fpath:
            r2 = dict(row)
            r2["strict_mandatory_ok"] = row["mandatory_ok"]
            r2["strict_has_morinus"] = False
            r2["strict_mandatory_miss_count"] = 999
            r2["strict_exception"] = "morinus_missing"
            strict_rows.append(r2)
            continue

        mor = parse_morinus_pd_file(Path(fpath))
        mor_full = set()
        for h in mor:
            if h.mode != "Z" or h.hit_date is None:
                continue
            mor_full.add(full_key(h.promissor, h.aspect, h.significator, h.direction, h.hit_date))

        strict_ok = True
        strict_miss_count = 0
        for mid in mandatory_ids:
            ev_hits = by_time_event.get((t, mid), [])
            has_exact = False
            for h in ev_hits:
                fk = (h["promissor"], h["aspect"], h["significator"], h["direction"], h["pd_date"])
                if fk in mor_full:
                    has_exact = True
                    break
            if not has_exact:
                strict_ok = False
                strict_miss_count += 1

        r2 = dict(row)
        r2["strict_mandatory_ok"] = strict_ok
        r2["strict_has_morinus"] = True
        r2["strict_mandatory_miss_count"] = strict_miss_count
        r2["strict_exception"] = "mandatory_partial_miss" if strict_miss_count > 0 else ""
        strict_rows.append(r2)

    # 순위는 기존 엔진 점수/규칙을 유지하고,
    # mandatory 미스는 번외 표시에만 사용한다.
    strict_rows.sort(
        key=lambda x: (
            not bool(x["mandatory_ok"]),
            x["max_uni_tier"],
            x["min_uni_tier"],
            -x["score"],
            x["time"],
        )
    )
    return strict_rows


def audit_morinus(case: dict[str, Any], top3: list[dict[str, Any]], audit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_time: dict[str, list[dict[str, Any]]] = {}
    for r in audit_rows:
        by_time.setdefault(r["time"], []).append(r)

    out: list[dict[str, Any]] = []
    target_times: list[str] = [r["time"] for r in top3]
    expected_time = str(case.get("expected_time", "") or "")
    if expected_time and expected_time not in target_times:
        target_times.append(expected_time)

    for t in target_times:
        fpath = case.get("morinus_files", {}).get(t)
        if not fpath:
            out.append({"case_id": case["case_id"], "time": t, "used": len(by_time.get(t, [])), "sig_match": "", "exact_match": "", "note": "missing morinus file"})
            continue
        mor = parse_morinus_pd_file(Path(fpath))
        mor_sig, mor_full = set(), set()
        for h in mor:
            if h.mode != "Z" or h.hit_date is None:
                continue
            mor_sig.add(signature_key(h.promissor, h.aspect, h.significator, h.direction))
            mor_full.add(full_key(h.promissor, h.aspect, h.significator, h.direction, h.hit_date))

        used = by_time.get(t, [])
        sig_ok = 0
        ex_ok = 0
        for u in used:
            sk = (u["promissor"], u["aspect"], u["significator"], u["direction"])
            fk = (u["promissor"], u["aspect"], u["significator"], u["direction"], u["pd_date"])
            if sk in mor_sig:
                sig_ok += 1
            if fk in mor_full:
                ex_ok += 1
        out.append(
            {
                "case_id": case["case_id"],
                "time": t,
                "used": len(used),
                "sig_match": sig_ok,
                "exact_match": ex_ok,
                "note": "",
            }
        )
    return out


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(IN_DEFAULT))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    top_path = OUT_DIR / "regression_top.csv"
    audit_path = OUT_DIR / "regression_event_pd.csv"
    mor_path = OUT_DIR / "regression_morinus_audit.csv"

    top_rows: list[dict[str, Any]] = []
    audit_rows_all: list[dict[str, Any]] = []
    mor_rows_all: list[dict[str, Any]] = []
    exceptions_rows: list[dict[str, Any]] = []
    expected_rows: list[dict[str, Any]] = []
    report_lines: list[str] = []

    for case in cfg["cases"]:
        # 절대 규칙: 최종 후보 순위는 항상 자체 PD 엔진 결과로 산출한다.
        # Morinus 파일은 엔진 오류 검증/고도화용 감사 자료로만 사용한다.
        events_for_case = parse_events(case["events"])
        ranked, audits = eval_case(case)
        main_ranked = [r for r in ranked if bool(r.get("mandatory_ok", False))]
        top3 = main_ranked[:3]
        expected_time = case.get("expected_time", "")
        expected_rank = ""
        if expected_time:
            for idx, row in enumerate(ranked, 1):
                if row["time"] == expected_time:
                    expected_rank = idx
                    break
        for i, r in enumerate(top3, 1):
            r2 = dict(r)
            r2["rank"] = i
            r2["expected_time"] = expected_time
            r2["expected_rank"] = expected_rank
            r2.setdefault("strict_mandatory_ok", r2.get("mandatory_ok", ""))
            r2.setdefault("strict_mandatory_miss_count", "")
            r2.setdefault("strict_exception", "")
            top_rows.append(r2)
        for r in ranked:
            if not bool(r.get("mandatory_ok", False)):
                exceptions_rows.append(
                    {
                        "case_id": case["case_id"],
                        "time": r["time"],
                        "score": r["score"],
                        "matched_count": r["matched_count"],
                        "mandatory_missing_count": "",
                        "missing_count": "",
                        "exception": "mandatory_missing",
                        "mandatory_missing_events": "",
                        "morinus_file": "",
                    }
                )
        expected_rows.append(
            {
                "case_id": case["case_id"],
                "expected_time": expected_time,
                "expected_rank": expected_rank,
                "top1": top3[0]["time"] if top3 else "",
                "top2": top3[1]["time"] if len(top3) > 1 else "",
                "top3": top3[2]["time"] if len(top3) > 2 else "",
            }
        )
        audit_rows_all.extend(audits)
        mor_rows_all.extend(audit_morinus(case, top3, audits))

        report_lines.append(f"## {case['case_id']}")
        if top3:
            report_lines.append("본순위")
            shown = top3
        else:
            report_lines.append("본순위: 없음")
            report_lines.append("번외(필수이벤트 미싱으로 수기검증 필요)")
            shown = ranked[:3]
        picked_by_time: dict[str, list[dict[str, Any]]] = {}
        for a in audits:
            picked_by_time.setdefault(a["time"], []).append(a)
        for idx, r in enumerate(shown, 1):
            report_lines.append(
                f"{idx}. {r['time']} | score={float(r['score']):.2f} | matched={r['matched_count']} | mandatory_ok={r.get('mandatory_ok', '')}"
            )
            mor_file = case.get("morinus_files", {}).get(r["time"])
            if mor_file:
                report_lines.append(f"Morinus 검증 파일: {mor_file}")
            report_lines.append("엔진 매칭 PD:")
            picked_for_time = picked_by_time.get(r["time"], [])
            if picked_for_time:
                for p in picked_for_time:
                    kind_tag = f"[{p.get('match_kind', 'Major')}] " if p.get("match_kind") else ""
                    report_lines.append(
                        "  - "
                        f"{p['event_id']}:{p['event_type']} | "
                        f"{kind_tag}{p['promissor']} {p['aspect']} {p['significator']} {p['direction']} | "
                        f"{p['pd_date']}"
                    )
            else:
                report_lines.append("  - 없음")
            # 미싱 이벤트 상세 (IMMUTABLE_RULES #4)
            matched_event_ids = {p["event_id"] for p in picked_for_time}
            missing = [e for e in events_for_case if e.id not in matched_event_ids]
            if missing:
                report_lines.append("미싱 이벤트:")
                for e in missing:
                    is_mand = e.et in MAND
                    flag = "  [필수미싱]" if is_mand else ""
                    report_lines.append(f"  - {e.id}:{e.et} ({e.y}-{e.m:02d}){flag}")
            mand_missing = [e for e in missing if e.et in MAND]
            report_lines.append(f"필수 미싱 여부: {'있음 (' + ', '.join(e.id for e in mand_missing) + ')' if mand_missing else '없음'}")
            report_lines.append("")

    with top_path.open("w", encoding="utf-8-sig", newline="") as f:
        top_fields = ["case_id", "rank", "time", "score", "matched_count", "mandatory_ok", "strict_mandatory_ok", "strict_mandatory_miss_count", "strict_exception", "min_uni_tier", "max_uni_tier", "expected_time", "expected_rank"]
        w = csv.DictWriter(f, fieldnames=top_fields)
        w.writeheader()
        for row in top_rows:
            w.writerow({k: row.get(k, "") for k in top_fields})
    with audit_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "time", "event_id", "event_type", "match_kind", "mode", "promissor", "aspect", "significator", "direction", "engine_arc", "pd_date", "raw_line"])
        w.writeheader()
        for row in audit_rows_all:
            row2 = dict(row)
            row2.setdefault("match_kind", "Major")
            row2.setdefault("mode", "")
            row2.setdefault("raw_line", "")
            row2.setdefault("engine_arc", "")
            w.writerow(row2)
    with mor_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "time", "used", "sig_match", "exact_match", "note"])
        w.writeheader()
        w.writerows(mor_rows_all)

    expected_path = OUT_DIR / "regression_expected_check.csv"
    with expected_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "expected_time", "expected_rank", "top1", "top2", "top3"])
        w.writeheader()
        w.writerows(expected_rows)

    print(top_path)
    print(audit_path)
    print(mor_path)
    print(expected_path)
    exceptions_path = OUT_DIR / "regression_exceptions.csv"
    with exceptions_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["case_id", "time", "score", "matched_count", "mandatory_missing_count", "missing_count", "exception", "mandatory_missing_events", "morinus_file"],
        )
        w.writeheader()
        w.writerows(exceptions_rows)
    print(exceptions_path)
    report_path = OUT_DIR / "regression_rank_report.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8-sig")
    print(report_path)


if __name__ == "__main__":
    main()
