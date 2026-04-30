from __future__ import annotations

from pathlib import Path

from rectification_engine.event_pipeline import write_payload_json


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    events_csv = root / "input" / "standardized_events_v2.csv"
    output_json = root / "input" / "event_matching_payload_v1.json"
    write_payload_json(events_csv, output_json, tolerance_months=2)
    print(output_json)


if __name__ == "__main__":
    main()
