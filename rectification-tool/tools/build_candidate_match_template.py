from __future__ import annotations

import argparse
import json
from pathlib import Path

from rectification_engine.event_pipeline import build_candidate_match_template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-id", required=True)
    parser.add_argument("--candidate-ids", required=True, help="Comma-separated IDs. e.g. BT_03:40,BT_03:41")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    payload_path = root / "input" / "event_matching_payload_v1.json"
    out_path = root / "input" / f"candidate_event_matches_{args.record_id}.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    candidate_ids = [x.strip() for x in args.candidate_ids.split(",") if x.strip()]
    out = build_candidate_match_template(payload, record_id=args.record_id, candidate_ids=candidate_ids)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
