from __future__ import annotations

import json
from collections import Counter
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
OUT_PATH = Path(__file__).resolve().parents[1] / "output" / "engine_vs_morinus_report.json"
ASPECTS = {"Conjunctio", "Sextil", "Quadrat", "Trigon", "Oppositio"}


def sign_candidates(aspect: str) -> list[int]:
    return [1] if aspect in {"Conjunctio", "Oppositio"} else [1, -1]


def try_calc(birth: BirthData, points: dict, hit, sign: int):
    promissor = canonical_point_name(hit.promissor)
    significator = canonical_point_name(hit.significator)
    if hit.mode != "Z":
        return None
    if hit.aspect not in ASPECTS:
        return None
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
    files = sorted(RANGE_FIXTURE.glob("*.txt"))
    total = 0
    supported = 0
    matched_direction = 0
    diffs = []
    unsupported_reasons = Counter()
    worst_rows = []

    for path in files:
        hhmm = f"{path.stem[:2]}:{path.stem[2:]}:25"
        birth = BirthData.from_strings("1981.10.13", hhmm, "morinus_0345")
        points = expand_antiscia(calculate_natal_points(birth))
        hits = parse_morinus_pd_file(path)

        for hit in hits:
            total += 1
            if hit.mode != "Z":
                unsupported_reasons["non_zodiacal"] += 1
                continue
            if hit.aspect not in ASPECTS:
                unsupported_reasons["unsupported_aspect"] += 1
                continue

            promissor = canonical_point_name(hit.promissor)
            significator = canonical_point_name(hit.significator)
            if promissor not in points:
                unsupported_reasons[f"missing_promissor:{promissor}"] += 1
                continue
            if significator not in points:
                unsupported_reasons[f"missing_significator:{significator}"] += 1
                continue

            best = None
            for s in sign_candidates(hit.aspect):
                try:
                    calc = try_calc(birth, points, hit, s)
                except Exception:
                    continue
                if calc is None:
                    continue
                diff = abs(calc.arc - float(hit.arc))
                ok_dir = calc.direction == hit.direction
                score = (0 if ok_dir else 1, diff)
                if best is None or score < best["score"]:
                    best = {
                        "score": score,
                        "diff": diff,
                        "dir_ok": ok_dir,
                        "sign": s,
                        "calc_dir": calc.direction,
                    }

            if best is None:
                unsupported_reasons["no_calc_path"] += 1
                continue

            supported += 1
            if best["dir_ok"]:
                matched_direction += 1
            diffs.append(best["diff"])
            worst_rows.append(
                {
                    "file": path.name,
                    "line": hit.raw_line,
                    "diff": best["diff"],
                    "dir_ok": best["dir_ok"],
                    "chosen_sign": best["sign"],
                    "expected_dir": hit.direction,
                    "calc_dir": best["calc_dir"],
                }
            )

    worst_rows.sort(key=lambda x: ((0 if x["dir_ok"] else 1) * -1, -x["diff"]))
    worst_rows = worst_rows[:50]
    diffs_sorted = sorted(diffs)
    report = {
        "files": len(files),
        "total_rows": total,
        "supported_rows": supported,
        "support_ratio": round(supported / total, 6) if total else 0.0,
        "direction_match_ratio": round(matched_direction / supported, 6) if supported else 0.0,
        "arc_diff_max": max(diffs) if diffs else None,
        "arc_diff_p95": diffs_sorted[int(len(diffs_sorted) * 0.95)] if diffs else None,
        "arc_diff_p50": diffs_sorted[int(len(diffs_sorted) * 0.5)] if diffs else None,
        "unsupported_reasons_top": unsupported_reasons.most_common(20),
        "worst_rows": worst_rows,
    }
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT_PATH)


if __name__ == "__main__":
    main()
