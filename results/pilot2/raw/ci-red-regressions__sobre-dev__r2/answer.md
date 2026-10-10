The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` ignored as you said. Two bugs were behind the failures, and I changed no tests.

- **Case visibility (`src/dispatch/database/service.py`):** `restricted_case_filter` listed `Case.visibility == restricted` as a standalone condition. Every restricted case therefore showed up for plain members, including ones they weren't a participant in. I made it match `restricted_incident_filter`: a restricted case is visible only if the user's email matches a participant.
- **Entity matching (`src/dispatch/entity/service.py`):** commit `beb60cc4` ("stop at the first JSONPath match") sliced the matches with `[:1]` in `find_entities`. That broke multi-match paths such as `asset[*].id`, which should yield one entity per match. I removed the slice. This restores the previous behavior, so the "perf" change is undone.

I haven't committed anything.