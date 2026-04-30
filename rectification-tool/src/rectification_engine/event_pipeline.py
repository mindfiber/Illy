from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
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

            # 대학 입학은 12~3월 윈도우를 함께 보관
            if e.event_type == "university_admission":
                event_item["season_window"] = {"month_start": 12, "month_end": 3, "cross_year": True}

            # 결혼/혼인 및 결혼 관련 표현은 통합 버킷으로 추가
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


def parse_year_month(date_text: str) -> tuple[int | None, int | None]:
    years = re.findall(r"(?:19|20)\d{2}", date_text or "")
    months = re.findall(r"(\d{1,2})월", date_text or "")
    year = int(years[0]) if years else None
    month = int(months[0]) if months else None
    return year, month


def write_payload_json(events_csv_path: str | Path, output_json_path: str | Path, tolerance_months: int = 2) -> None:
    events = load_standardized_events(events_csv_path)
    payload = to_matching_payload(events, tolerance_months=tolerance_months)
    Path(output_json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
