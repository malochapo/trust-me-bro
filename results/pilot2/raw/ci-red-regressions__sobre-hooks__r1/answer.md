The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` left out as you said. Two bugs were behind the two failing tests, and I didn't touch any tests.

- **Case visibility** (`src/dispatch/database/service.py`): `restricted_case_filter` let members see every restricted case, because the participant-email check sat in the same `or_` as the visibility checks. It now requires the case to be restricted and the user to be a participant, the same as `restricted_incident_filter`.
- **Entity extraction** (`src/dispatch/entity/service.py`): commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]` to `find_entities`. That dropped all but the first match for paths like `asset[*].id`, so I reverted that change.

I haven't committed anything.