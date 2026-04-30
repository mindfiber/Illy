# Rectification Engine Specification

## Purpose

The rectification tool searches a birth-time range and returns the most likely birth-time candidates by comparing user-supplied life events with Morinus-style primary direction hit lists.

The engine must perform calculation and structure only. It must not add interpretive judgment beyond the event-to-indicator mapping rules explicitly defined in this project.

## Target Workflow

1. Receive birth data:
   - date
   - place
   - timezone
   - birth-time range
2. Receive event records:
   - event date or date range
   - event category
   - optional notes
3. Normalize event windows.
4. Generate birth-time candidates at 1-minute resolution.
5. If the birth-time range is 2 hours or wider, apply the Jupiter ingress pre-filter first.
6. For each remaining candidate, calculate the primary direction hit list.
7. Filter hits around each event window.
8. Match event categories to allowed direction indicators.
9. Score candidates by matched event count and tie-break rules.
10. Output the top 1, 2, and 3 candidate groups.

## Fixed Calculation Rules

- Primary direction method: Morinus-compatible primary directions.
- House/arc framework: Placidus semi-arc.
- Direction types: zodiacal and mundane.
- Motion types: direct and converse.
- Key: Naibod.
- Naibod value: `0.9855555556`.
- Latitude setting: neither.
- Secondary motion: not used.
- Planets: traditional seven planets only.
- Outer planets, Chiron, asteroids, and modern rulers are excluded.
- Antiscia and contra-antiscia are included.
- Major aspects only:
  - conjunction
  - sextile
  - square
  - trine
  - opposition
- ASC, MC, and Lot of Fortune are treated as angle-level points.
- ASC, MC, and Lot of Fortune may be used as promissors and significators.

## Points

Base celestial points:

- Sun
- Moon
- Mercury
- Venus
- Mars
- Jupiter
- Saturn

Angle-level points:

- ASC
- MC
- Lot of Fortune

Derived points:

- antiscia of allowed base and angle-level points
- contra-antiscia of allowed base and angle-level points

Open decision:

- Whether DSC and IC should be explicit independent points or only represented through opposition to ASC/MC must be verified against Morinus output.

## Candidate Generation

- Candidate birth times are generated at 1-minute resolution.
- Candidate range comes from the user input or normalized birth-time expression.
- Candidate IDs must be stable and deterministic.
- Candidate generation must not skip minutes unless a documented pre-filter is active.

## Event Window Rules

Default rule:

- Event windows allow plus/minus 2 months.

University admission rule:

- University admission, university entrance, acceptance, or enrollment events are searched from December of the previous year through March of the event year.

Marriage rule:

- Marriage is handled as one integrated event category.
- Wedding, legal marriage registration, and marriage ceremony records should not be treated as unrelated categories unless the user explicitly separates them.

Wide birth-time range rule:

- If the birth-time range is 2 hours or wider, Jupiter ingress filtering is applied before full 1-minute PD scoring.

## PD Hit List Requirements

Each generated PD hit must retain enough information to compare against Morinus exports:

- candidate birth time
- direction date
- arc
- zodiacal or mundane mode
- direct or converse
- promissor
- significator
- aspect
- point modifiers, if any:
  - antiscia
  - contra-antiscia
- calculation notes needed for debugging

The engine must be able to emit an unfiltered full hit list for a candidate. Event matching and scoring must be separate from PD calculation.

## Matching Rules

Event matching is a rule-based comparison, not free interpretation.

Required matching sequence:

1. Normalize the event category.
2. Map the event category to allowed planetary or angular indicators.
3. Search for angle-level hits inside the event window first.
4. If no angle-level hit exists, search allowed planet-to-planet major directions.
5. Lower-priority event matches must not override higher-priority event matches.

Open decision:

- The exact event-category-to-indicator table must be reviewed and rewritten in clean UTF-8 before implementation.

## Candidate Ranking

Primary ranking:

- number of matched events

Secondary ranking, to be finalized:

- number of high-priority events matched
- closeness of hit date to event date or event window center
- angle-level hits before planet-to-planet hits
- fewer unsupported or weak matches

The ranking system must output:

- rank 1 candidate group
- rank 2 candidate group
- rank 3 candidate group

If multiple adjacent birth minutes produce equivalent scores, the output should preserve them as a candidate group rather than pretending one minute is uniquely selected.

## Morinus Verification Strategy

The new engine should be developed against manually saved Morinus PD lists.

For each verification case, provide:

- birth date
- exact test birth time
- birthplace
- timezone
- Morinus settings used
- Morinus PD text export or manually saved list
- whether the export is zodiacal, mundane, or both
- whether direct and converse are both included
- arc/date precision shown in Morinus

The first milestone is not event matching. The first milestone is reproducing Morinus PD rows for one known chart within an acceptable tolerance.

## Fixture Format

Preferred fixture layout:

```text
tests/fixtures/morinus_case_001/
  birth.json
  morinus_pd_raw.txt
  expected_hits.csv
  notes.md
```

`birth.json` should contain:

```json
{
  "name": "case_001",
  "birth_date": "YYYY-MM-DD",
  "birth_time": "HH:MM",
  "timezone": "Asia/Seoul",
  "place": "Seoul",
  "latitude": 37.5665,
  "longitude": 126.9780
}
```

`expected_hits.csv` should contain normalized columns:

```csv
date,arc,mode,direction,promissor,significator,aspect,raw_line
```

If Morinus output cannot be normalized immediately, store the raw text first and normalize it later.

## Build Order

1. Write fixture parser for Morinus PD text exports.
2. Implement event window normalization.
3. Implement 1-minute candidate generation.
4. Implement natal point calculation.
5. Implement zodiacal PD calculation and compare against Morinus.
6. Implement mundane PD calculation and compare against Morinus.
7. Implement direct/converse handling and compare against Morinus.
8. Implement hit filtering by event window.
9. Implement event-category indicator matching.
10. Implement candidate scoring and top-3 output.
11. Implement Jupiter ingress pre-filter.
12. Add UI/export only after the engine is verified.

## Current Unknowns

The following items require user-supplied Morinus reference data before implementation can be considered verified:

- exact Morinus PD settings screen values
- whether Morinus output includes or excludes DSC/IC as separate rows
- exact naming conventions in Morinus rows
- date and arc precision
- direct/converse labeling
- zodiacal/mundane labeling
- how Morinus displays antiscia and contra-antiscia rows
- whether Lot of Fortune is calculated day/night exactly as expected by this project

