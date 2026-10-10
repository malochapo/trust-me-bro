The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` ignored as you said. Two bugs were behind the failures, and I didn't touch any tests.

- **Case visibility** (`src/dispatch/database/service.py`): `restricted_case_filter` let members see every restricted case. The restricted check wasn't tied to the participant email check, so any restricted case matched. I wrapped the two in `and_`, the same way `restricted_incident_filter` does it. Members now see open cases plus restricted cases they take part in. This was a permissions leak, not just a test failure.
- **Entity extraction** (`src/dispatch/entity/service.py`): commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]` to `find_entities`. That dropped every match after the first when one path matches several fields. I reverted that line.

I didn't commit anything.