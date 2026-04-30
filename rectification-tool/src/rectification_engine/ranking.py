from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventMatch:
    event_id: str
    matched: bool
    abs_month_diff: float
    weight: float = 1.0


@dataclass(frozen=True)
class CandidateScore:
    candidate_id: str
    total_score: float
    matched_count: int
    mean_abs_month_diff: float


def score_event(match: EventMatch, tolerance_months: float = 2.0) -> float:
    if not match.matched:
        return 0.0
    if tolerance_months <= 0:
        return match.weight
    decay = max(0.0, 1.0 - (match.abs_month_diff / tolerance_months))
    return match.weight * decay


def score_candidate(
    candidate_id: str,
    matches: list[EventMatch],
    tolerance_months: float = 2.0,
) -> CandidateScore:
    total = 0.0
    matched_count = 0
    sum_abs_diff = 0.0
    for m in matches:
        s = score_event(m, tolerance_months=tolerance_months)
        total += s
        if m.matched:
            matched_count += 1
            sum_abs_diff += m.abs_month_diff

    mean_diff = (sum_abs_diff / matched_count) if matched_count > 0 else 999.0
    return CandidateScore(
        candidate_id=candidate_id,
        total_score=round(total, 6),
        matched_count=matched_count,
        mean_abs_month_diff=round(mean_diff, 6),
    )


def rank_candidates(
    candidate_matches: dict[str, list[EventMatch]],
    tolerance_months: float = 2.0,
    top_k: int = 3,
) -> list[CandidateScore]:
    scored = [
        score_candidate(candidate_id, matches, tolerance_months=tolerance_months)
        for candidate_id, matches in candidate_matches.items()
    ]
    scored.sort(key=lambda x: (-x.total_score, -x.matched_count, x.mean_abs_month_diff, x.candidate_id))
    return scored[:top_k]
