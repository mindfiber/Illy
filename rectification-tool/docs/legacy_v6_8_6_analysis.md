# Legacy v6.8.6 Analysis

## Source Package

Imported from:

- `E:/Sujin/Illy/BirthtimeEngine/BirthtimeEngine.zip`

Selected files were copied into:

- `rectification-tool/legacy/v6.8.6/`

Large generated files were intentionally not imported:

- `build/`
- `dist/`
- packaged `.exe`
- nested zip outputs

## Intended Tool Behavior

The target tool should:

1. Use the Morinus primary direction calculation method.
2. Take the user's birth-time range and event list as input.
3. Generate candidate birth times at 1-minute resolution.
4. For each event date or event window, search nearby primary direction hits.
5. Compare event topics against direction indicators.
6. Rank candidate birth times by the number and quality of matched events.
7. Return the top 1, 2, and 3 birth-time candidates.
8. If the birth-time range is wider than 2 hours, use Jupiter ingress filtering first.

Project-level constraints still apply:

- Placidus semi-arc primary directions.
- Zodiacal and mundane directions.
- Naibod key: `0.9855555556`.
- ASC, MC, and Lot of Fortune are treated as angles.
- Event windows allow plus/minus 2 months.
- University admission events use December through March.
- Marriage events are handled as an integrated event category.

## What The Legacy Script Actually Does

The main source file is:

- `rectification-tool/legacy/v6.8.6/EXE_PD_engine_v6.8.6_MZFIX_FIXED2.py`

Observed behavior:

- Candidate step defaults to 2 minutes, with optional 1-minute offset merging.
- The PD hit list is generated inside `compute_pd_hits_for_candidate`.
- The Naibod value is `0.985647`, not the project rule `0.9855555556`.
- The code uses Swiss Ephemeris Placidus houses for ASC/MC.
- It includes ASC, MC, Lot of Fortune, DSC, and IC in both promissor and significator sets.
- It expands both promissors and significators with antiscia and contra-antiscia.
- It computes a simple RA difference for zodiacal and an "equatorial-style" RA aspect for mundane.
- It converts every arc into a forward date from the birth date.
- It labels two directions as `D` and `C`, but both are projected forward in time.
- It only filters generated hits by event month windows.
- It does not rank birth-time candidates into top 1, 2, and 3.
- It does not implement event-topic indicator matching in the imported Python file.
- It sets `jupiter_ingress.use` from whether key-event text exists, but no Jupiter ingress pre-filter implementation was found in the main flow.

## Key Risks

- The PD calculation is not a faithful Morinus semi-arc implementation yet.
- Mundane directions are not implemented as Placidus semi-arc mundane directions.
- Direct/converse handling is likely only a geometric reverse-arc search, not a complete directional model.
- Event matching is currently window filtering, not semantic event-indicator matching.
- Candidate ranking is absent from the legacy source.
- Korean text in several legacy files appears mojibake in the terminal, so parsing/event keyword rules should be rewritten cleanly in UTF-8 instead of patched in place.

## Recommended Rebuild Plan

1. Keep the legacy script as a reference only.
2. Build a clean Python package under `rectification-tool/src/`.
3. Separate modules by responsibility:
   - input parsing
   - event window normalization
   - natal chart calculation
   - Morinus PD calculation
   - PD hit filtering
   - event-indicator matching
   - candidate scoring and ranking
   - reports/export
4. Add fixture cases from Morinus or trusted exported PD logs before changing calculation logic.
5. Implement the PD engine first, then event matching, then ranking.
6. Only add UI or packaging after the engine produces verified hit lists.

## Immediate Next Step

Create a minimal engine skeleton and test fixture harness:

- `src/rectification_engine/`
- `tests/fixtures/`
- `tests/test_event_windows.py`
- `tests/test_pd_against_reference.py`

The first milestone should be reproducing a small Morinus PD hit list for a known chart before candidate ranking is attempted.
