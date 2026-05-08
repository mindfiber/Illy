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
NAI = 0.9855555556
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
            sy, sm = e.y - 1, 12
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


def arc_date(bdt: datetime, arc: float) -> date:
    return (bdt + timedelta(days=(arc / NAI) * 365.2422 - 2.15)).date()


def allowed(et: str) -> set[str]:
    if et in {"university_admission", "graduate_school_admission", "employment_start", "first_employment", "promotion_award", "career_honor_event", "graduation", "marriage", "childbirth", "relationship"}:
        return BENEFICS
    if et in {"employment_end", "dropout", "family_death", "surgery_medical_major", "mental_health_crisis"}:
        return MALEFICS
    return BENEFICS | MALEFICS


def pa_ap(p: str, s: str) -> bool:
    pA = any(a in p for a in ANGLE)
    sA = any(a in s for a in ANGLE)
    pP = any(x in p for x in PLANETS)
    sP = any(x in s for x in PLANETS)
    return (pP and sA and not pA and not sP) or (sP and pA and not sA and not pP)


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
    bdt = datetime.combine(b.birth_date, b.birth_time)
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
                            gen.append((p, a, s, c.direction, c.arc, arc_date(bdt, c.arc)))
                        except Exception:
                            pass
                    if significator_can_receive_aspected(s):
                        try:
                            c = zodiacal_promissor_to_significator_aspect(b, p, s, a, sg, pts)
                            gen.append((p, a, s, c.direction, c.arc, arc_date(bdt, c.arc)))
                        except Exception:
                            pass
        for a in ASPECTS:
            signs = [1] if a in ("Conjunctio", "Oppositio") else SIGNS
            for sg in signs:
                for angle in ("ASC", "MC"):
                    try:
                        c = zodiacal_promissor_aspect_to_angle(b, p, a, sg, angle, pts)
                        gen.append((p, a, angle, c.direction, c.arc, arc_date(bdt, c.arc)))
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

    for mm in range(sM, eM + 1):
        hh, mi = mm // 60, mm % 60
        hhmm = f"{hh:02d}:{mi:02d}"
        b = BirthData(date(y, m, d), time(hh, mi, birth_second), place)
        gen = generate_pd_hits(b)
        matched = []
        mand_ok = True
        uni_tiers = []
        for ev in events:
            ws, we = win(ev)
            aset = allowed(ev.et)
            hits = [g for g in gen if pa_ap(g[0], g[2]) and ws <= g[5] <= we and any(p in g[0] or p in g[2] for p in aset)]
            hits.sort(key=lambda x: (admission_month_tier(ev, x[5]), x[5], abs(x[4])))
            ok = bool(hits)
            if ev.et in MAND and not ok:
                mand_ok = False
            if ok:
                picked = hits[:3]
                matched.append((ev, picked))
                if ev.et == "university_admission":
                    uni_tiers.append(admission_month_tier(ev, picked[0][5]))
            for h in hits[:3]:
                audit_rows.append(
                    {
                        "case_id": case["case_id"],
                        "time": hhmm,
                        "event_id": ev.id,
                        "event_type": ev.et,
                        "promissor": normalize_point_name(h[0]),
                        "aspect": h[1],
                        "significator": normalize_point_name(h[2]),
                        "direction": h[3],
                        "engine_arc": round(float(h[4]), 6),
                        "pd_date": h[5].isoformat(),
                    }
                )
        score = 0.0
        for ev, hs in matched:
            base = event_base_weight(ev)
            base -= 0.5 * admission_month_tier(ev, hs[0][5])
            base *= career_weight(ev)
            score += base
        score += sum(0.25 * len(hs) for _, hs in matched)
        max_uni_tier = max(uni_tiers) if uni_tiers else 9
        min_uni_tier = min(uni_tiers) if uni_tiers else 9
        score_rows.append(
            {
                "case_id": case["case_id"],
                "time": hhmm,
                "score": round(score, 4),
                "matched_count": len(matched),
                "mandatory_ok": mand_ok,
                "min_uni_tier": min_uni_tier,
                "max_uni_tier": max_uni_tier,
            }
        )
    score_rows.sort(key=lambda x: (not x["mandatory_ok"], x["max_uni_tier"], x["min_uni_tier"], -x["score"], x["time"]))
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
                    report_lines.append(
                        "  - "
                        f"{p['event_id']}:{p['event_type']} | "
                        f"{p.get('mode', '')} {p['promissor']} {p['aspect']} {p['significator']} {p['direction']} | "
                        f"{p['pd_date']}"
                    )
            else:
                report_lines.append("  - 없음")
            report_lines.append("미싱/필수미싱 상세는 후보별 이벤트 매칭 산출 단계에서 보강 필요")
            report_lines.append("")

    with top_path.open("w", encoding="utf-8-sig", newline="") as f:
        top_fields = ["case_id", "rank", "time", "score", "matched_count", "mandatory_ok", "strict_mandatory_ok", "strict_mandatory_miss_count", "strict_exception", "min_uni_tier", "max_uni_tier", "expected_time", "expected_rank"]
        w = csv.DictWriter(f, fieldnames=top_fields)
        w.writeheader()
        for row in top_rows:
            w.writerow({k: row.get(k, "") for k in top_fields})
    with audit_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "time", "event_id", "event_type", "mode", "promissor", "aspect", "significator", "direction", "engine_arc", "pd_date", "raw_line"])
        w.writeheader()
        for row in audit_rows_all:
            row2 = dict(row)
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
