# Build Notes

## Stable Snapshot

Version: v6.8.5 rebuild3 FIXED

## Fixed

- TSV multiline paste restored
- json.dumps used for event storage
- date parsing restricted to YYYY.MM.DD / YYYY-MM-DD / YYYY/MM/DD
- Path handling unified
- datetime import issue fixed
- zip output confirmed
- pd_hits.csv output confirmed

## Build Environment

- Windows
- Python 3.11
- PyInstaller onefile/windowed
- assets included via `--add-data "assets;assets"`

## Next Work

- Use latest generated ZIP
- Inspect `pd_hits.csv`
- Confirm hit count
- Rank candidates by event match
