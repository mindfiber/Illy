from __future__ import annotations

from datetime import time

from .models import Candidate


def _to_minutes(hhmm: str) -> int:
    hh, mm = [int(part) for part in hhmm.split(":")]
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"Invalid time: {hhmm}")
    return hh * 60 + mm


def _to_time(total_minutes: int) -> time:
    if not (0 <= total_minutes <= 1439):
        raise ValueError(f"Minute outside day: {total_minutes}")
    return time(total_minutes // 60, total_minutes % 60)


def generate_minute_candidates(start_hhmm: str, end_hhmm: str) -> list[Candidate]:
    start = _to_minutes(start_hhmm)
    end = _to_minutes(end_hhmm)
    if end < start:
        raise ValueError("Birth-time candidate range cannot cross midnight yet.")

    candidates: list[Candidate] = []
    for minute in range(start, end + 1):
        hhmm = f"{minute // 60:02d}:{minute % 60:02d}"
        candidates.append(Candidate(candidate_id=f"BT_{hhmm}", birth_time=_to_time(minute)))
    return candidates

