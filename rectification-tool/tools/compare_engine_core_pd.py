from __future__ import annotations

import json
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


RANGE_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "morinus_0325_0405"
OUT_PATH = Path(__file__).resolve().parents[1] / "output" / "engine_vs_morinus_core_report.json"
ASPECTS = {"Conjunctio", "Sextil", "Quadrat", "Trigon", "Oppositio"}
CORE_PLANETS = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
CORE_ANGLES = {"ASC", "MC", "LoF"}


def sign_candidates(aspect: str) -> list[int]:
    return [1] if aspect in {"Conjunctio", "Oppositio"} else [1, -1]


def is_core_row(hit) -> bool:
    if hit.mode != "Z" or hit.aspect not in ASPECTS:
        return False
    p = canonical_point_name(hit.promissor)
    s = canonical_point_name(hit.significator)
    # 실전 대조 핵심: 주요행성 + 앵글 디렉션 위주
    token_match = any(x in p for x in CORE_PLANETS) or any(x in s for x in CORE_PLANETS)
    angle_match = any(x in p for x in CORE_ANGLES) or any(x in s for x in CORE_ANGLES)
    return token_match and angle_match


def try_calc(birth: BirthData, points: dict, hit, sign: int):
    promissor = canonical_point_name(hit.promissor)
    significator = canonical_point_name(hit.significator)
    if promissor not in points or significator not in points:
        return None
    if significator == "MC" and hit.aspect_side == "promissor":
        return zodiacal_promissor_aspect_to_mc(
            birth=birth,
            promissor_name=promissor,
            aspect_name=hit.aspect,
            aspect_sign=sign,
            points=points,
        )
    if hit.aspect_side == "promissor":
        return zodiacal_promissor_aspect_to_significator(
            birth=birth,
            promissor_name=promissor,
            aspect_name=hit.aspect,
            aspect_sign=sign,
            significator_name=significator,
            points=points,
        )
    return zodiacal_promissor_to_significator_aspect(
        birth=birth,
        promissor_name=promissor,
        significator_name=significator,
        aspect_name=hit.aspect,
        aspect_sign=sign,
        points=points,
    )


def main() -> None:
    diffs = []
    dir_ok = 0
    total = 0
    bad_rows = []

    for path in sorted(RANGE_FIXTURE.glob("*.txt")):
        hhmm = f"{path.stem[:2]}:{path.stem[2:]}:25"
        birth = BirthData.from_strings("1981.10.13", hhmm, "morinus_0345")
        points = expand_antiscia(calculate_natal_points(birth))
        hits = parse_morinus_pd_file(path)
        for hit in hits:
            if not is_core_row(hit):
                continue
            total += 1
            best = None
            for s in sign_candidates(hit.aspect):
                try:
                    calc = try_calc(birth, points, hit, s)
                except Exception:
                    continue
                if calc is None:
                    continue
                diff = abs(calc.arc - float(hit.arc))
                ok = calc.direction == hit.direction
                score = (0 if ok else 1, diff)
                if best is None or score < best["score"]:
                    best = {"diff": diff, "ok": ok, "score": score, "line": hit.raw_line}
            if best is None:
                continue
            diffs.append(best["diff"])
            if best["ok"]:
                dir_ok += 1
            else:
                bad_rows.append(best["line"])

    diffs.sort()
    report = {
        "core_rows": total,
        "direction_match_ratio": round(dir_ok / total, 6) if total else 0.0,
        "arc_diff_p50": diffs[int(len(diffs) * 0.5)] if diffs else None,
        "arc_diff_p95": diffs[int(len(diffs) * 0.95)] if diffs else None,
        "arc_diff_max": max(diffs) if diffs else None,
        "direction_mismatch_examples": bad_rows[:30],
    }
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT_PATH)


if __name__ == "__main__":
    main()
