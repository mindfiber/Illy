from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class StandardizedEvent:
    record_id: str
    client_name: str
    gender: str
    birth_range_text: str
    location_text: str
    source_column: str
    raw_fragment: str
    event_type: str
    event_polarity: str
    date_text: str
    date_precision: str


def load_standardized_events(path: str | Path) -> list[StandardizedEvent]:
    rows: list[StandardizedEvent] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(
                StandardizedEvent(
                    record_id=r["record_id"],
                    client_name=r["client_name"],
                    gender=r["gender"],
                    birth_range_text=r["birth_range_text"],
                    location_text=r["location_text"],
                    source_column=r["source_column"],
                    raw_fragment=r["raw_fragment"],
                    event_type=r["event_type"],
                    event_polarity=r["event_polarity"],
                    date_text=r["date_text"],
                    date_precision=r["date_precision"],
                )
            )
    return rows


def parse_year_month(date_text: str) -> tuple[int | None, int | None]:
    years = re.findall(r"(?:19|20)\d{2}", date_text or "")
    # month-like token, first one wins
    months = re.findall(r"(?<!\d)(1[0-2]|0?[1-9])(?!\d)", date_text or "")
    year = int(years[0]) if years else None
    month = int(months[0]) if months else None
    return year, month


def _parse_range_days(text: str) -> int | None:
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


def _career_weight(raw_fragment: str, event_type: str) -> float:
    if event_type not in {"career_honor_event", "employment_start", "first_employment"}:
        return 1.0
    days = _parse_range_days(raw_fragment)
    if days is None:
        return 1.0
    if days >= 365:
        return 1.0
    if days >= 180:
        return 0.6
    return 0.3


def to_matching_payload(events: list[StandardizedEvent], tolerance_months: int = 2) -> dict:
    grouped: dict[str, list[StandardizedEvent]] = defaultdict(list)
    for e in events:
        grouped[e.record_id].append(e)

    records = []
    for record_id, rows in grouped.items():
        first = rows[0]
        payload_events = []
        marriage_bucket = []

        for e in rows:
            y, m = parse_year_month(e.date_text)
            event_item = {
                "event_type": e.event_type,
                "event_polarity": e.event_polarity,
                "date_text": e.date_text,
                "date_precision": e.date_precision,
                "year": y,
                "month": m,
                "source_column": e.source_column,
                "raw_fragment": e.raw_fragment,
                "tolerance_months": tolerance_months,
            }
            if e.event_type == "university_admission":
                event_item["season_window"] = {"month_start": 12, "month_end": 3, "cross_year": True}
            if e.event_type == "marriage":
                marriage_bucket.append(event_item)
            payload_events.append(event_item)

        if marriage_bucket:
            payload_events.append(
                {
                    "event_type": "marriage_merged",
                    "merged_count": len(marriage_bucket),
                    "members": marriage_bucket,
                    "tolerance_months": tolerance_months,
                }
            )

        records.append(
            {
                "record_id": record_id,
                "client_name": first.client_name,
                "gender": first.gender,
                "birth_range_text": first.birth_range_text,
                "location_text": first.location_text,
                "events": payload_events,
            }
        )
    return {"version": 1, "records": records}


def write_payload_json(events_csv_path: str | Path, output_json_path: str | Path, tolerance_months: int = 2) -> None:
    events = load_standardized_events(events_csv_path)
    payload = to_matching_payload(events, tolerance_months=tolerance_months)
    Path(output_json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def infer_child_indicator(raw_fragment: str) -> str:
    text = raw_fragment or ""
    if "아들" in text:
        return "son"
    if "딸" in text:
        return "daughter"
    if "수성" in text:
        return "mercury"
    return ""


def infer_is_major_k_event(raw_fragment: str, source_column: str) -> bool:
    if source_column != "K":
        return False
    text = raw_fragment or ""
    major_keywords = ["큰", "대수술", "전신마취", "중환자실", "골절", "압박", "교통사고", "외상", "수술", "절개"]
    return any(k in text for k in major_keywords)


def build_candidate_match_template(
    payload: dict,
    record_id: str,
    candidate_ids: list[str],
    tolerance_months: int = 2,
    max_g_misses: int = 2,
) -> dict:
    record = next((r for r in payload.get("records", []) if r.get("record_id") == record_id), None)
    if record is None:
        raise ValueError(f"Record not found: {record_id}")

    event_rows = []
    for idx, e in enumerate(record.get("events", []), start=1):
        if e.get("event_type") == "marriage_merged":
            continue
        event_type = str(e.get("event_type", ""))
        source_column = str(e.get("source_column", ""))
        raw_fragment = str(e.get("raw_fragment", ""))
        event_rows.append(
            {
                "event_id": f"{record_id}_evt_{idx:04d}",
                "source_column": source_column,
                "event_type": event_type,
                "is_major": infer_is_major_k_event(raw_fragment, source_column),
                "is_family_death": event_type == "family_death",
                "is_marriage": event_type in {"marriage", "marriage_merged"},
                "is_childbirth": event_type == "childbirth",
                "child_indicator": infer_child_indicator(raw_fragment) if event_type == "childbirth" else "",
                "weight": _career_weight(raw_fragment, event_type),
            }
        )

    candidates = []
    for cid in candidate_ids:
        candidates.append(
            {
                "candidate_id": cid,
                "event_matches": [
                    {
                        **e,
                        "matched": False,
                        "abs_month_diff": 999.0,
                        "weight": float(e.get("weight", 1.0)),
                    }
                    for e in event_rows
                ],
            }
        )

    return {
        "tolerance_months": tolerance_months,
        "top_k": 3,
        "max_g_misses": max_g_misses,
        "record_id": record_id,
        "client_name": record.get("client_name", ""),
        "candidates": candidates,
    }
