# Branch Strategy

Use only a small set of long-lived branches:

- `main`: stable project baseline and shared documentation.
- `rectification`: birth-time rectification tool development.
- `reading`: chart interpretation notes and reading work.
- `class`: curriculum, lessons, and teaching material.

Do not create separate branches for each rectification subtopic unless there is a large isolated experiment. For ordinary work, keep PD calculation, Morinus comparison, event mapping, candidate ranking, and UI packaging together on `rectification` so the tool can be tested end to end.

