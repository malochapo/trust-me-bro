The suite is green: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you asked. I didn't change any tests.

There were two real bugs, each from a recent commit:

1. **Member case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`): commit `42699ebc` ("flatten the restricted case filter") removed the `and_` around the restricted-visibility check. That made every restricted case visible to members, not just those where the user is a participant. I restored the `and_(Case.visibility == restricted, IndividualContact.email == user.email)` grouping.

2. **JSONPath matches** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`): commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]`, which dropped every match after the first. That broke `asset[*].id`, which should yield one entity per matching element. I removed the slice so all matches are kept.

I didn't commit anything. The `beb60cc4` commit message says the change was a perf optimization, so if you want the speedup back, it needs a different approach that still returns all matches.