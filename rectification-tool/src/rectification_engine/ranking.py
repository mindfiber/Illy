from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventMatch:
    event_id: str
    matched: bool
    abs_month_diff: float
    weight: float = 1.0
    source_column: str = ""
    event_type: str = ""
    is_major: bool = False
    is_family_death: bool = False
    is_marriage: bool = False


@dataclass(frozen=True)
class CandidateScore:
    candidate_id: str
    total_score: float
    matched_count: int
    mean_abs_month_diff: float
    eligible: bool = True
    disqualify_reasons: tuple[str, ...] = ()


def hard_requirements_ok(
    matches: list[EventMatch],
    max_g_misses: int = 2,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    g_rows = [m for m in matches if m.source_column == "G"]
    if g_rows:
        g_miss = sum(1 for m in g_rows if not m.matched)
        if g_miss > max_g_misses:
            reasons.append(f"G_miss_exceeded:{g_miss}>{max_g_misses}")

    h_marriage_rows = [m for m in matches if m.source_column == "H" and (m.is_marriage or m.event_type in {"marriage", "marriage_merged"})]
    if h_marriage_rows and not any(m.matched for m in h_marriage_rows):
        reasons.append("H_marriage_required_unmatched")

    l_family_death_rows = [m for m in matches if m.source_column == "L" and (m.is_family_death or m.event_type == "family_death")]
    if l_family_death_rows and not all(m.matched for m in l_family_death_rows):
        reasons.append("L_family_death_unmatched")

    k_major_rows = [m for m in matches if m.source_column == "K" and m.is_major]
    if k_major_rows and not all(m.matched for m in k_major_rows):
        reasons.append("K_major_event_unmatched")

    return len(reasons) == 0, reasons


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
    max_g_misses: int = 2,
) -> CandidateScore:
    eligible, reasons = hard_requirements_ok(matches, max_g_misses=max_g_misses)
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
        eligible=eligible,
        disqualify_reasons=tuple(reasons),
    )


def rank_candidates(
    candidate_matches: dict[str, list[EventMatch]],
    tolerance_months: float = 2.0,
    top_k: int = 3,
    max_g_misses: int = 2,
) -> list[CandidateScore]:
    scored = [
        score_candidate(candidate_id, matches, tolerance_months=tolerance_months, max_g_misses=max_g_misses)
        for candidate_id, matches in candidate_matches.items()
    ]
    scored = [s for s in scored if s.eligible]
    scored.sort(key=lambda x: (-x.total_score, -x.matched_count, x.mean_abs_month_diff, x.candidate_id))
    return scored[:top_k]
