from __future__ import annotations

import json
from pathlib import Path

from rectification_engine.ranking import EventMatch, rank_candidates


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    in_path = root / "input" / "candidate_event_matches_v1.json"
    out_path = root / "output" / "top_candidates_v1.json"

    payload = json.loads(in_path.read_text(encoding="utf-8"))
    tolerance_months = float(payload.get("tolerance_months", 2.0))
    top_k = int(payload.get("top_k", 3))
    max_g_misses = int(payload.get("max_g_misses", 2))

    candidate_matches: dict[str, list[EventMatch]] = {}
    for c in payload.get("candidates", []):
        cid = c["candidate_id"]
        matches = []
        for m in c.get("event_matches", []):
            matches.append(
                EventMatch(
                    event_id=str(m.get("event_id", "")),
                    matched=bool(m.get("matched", False)),
                    abs_month_diff=float(m.get("abs_month_diff", 999.0)),
                    weight=float(m.get("weight", 1.0)),
                    source_column=str(m.get("source_column", "")),
                    event_type=str(m.get("event_type", "")),
                    is_major=bool(m.get("is_major", False)),
                    is_family_death=bool(m.get("is_family_death", False)),
                    is_marriage=bool(m.get("is_marriage", False)),
                    is_childbirth=bool(m.get("is_childbirth", False)),
                    child_indicator=str(m.get("child_indicator", "")),
                )
            )
        candidate_matches[cid] = matches

    top = rank_candidates(
        candidate_matches,
        tolerance_months=tolerance_months,
        top_k=top_k,
        max_g_misses=max_g_misses,
    )
    out = {
        "tolerance_months": tolerance_months,
        "top_k": top_k,
        "max_g_misses": max_g_misses,
        "top_candidates": [
            {
                "rank": i + 1,
                "candidate_id": c.candidate_id,
                "total_score": c.total_score,
                "matched_count": c.matched_count,
                "mean_abs_month_diff": c.mean_abs_month_diff,
                "eligible": c.eligible,
                "disqualify_reasons": list(c.disqualify_reasons),
                "mercury_child_match_count": c.mercury_child_match_count,
            }
            for i, c in enumerate(top)
        ],
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
