The suite is green: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you asked. Both failures came from recent commits that broke working behaviour, and I fixed each at its source without touching any tests.

- **Restricted case visibility** (`src/dispatch/database/service.py`): commit 42699ebc "flattened" `restricted_case_filter` by removing the `and_`. That made every restricted case visible to members, not just the ones they participate in. I restored the `and_(Case.visibility == restricted, IndividualContact.email == user.email)` clause.
- **Entity JSONPath matches** (`src/dispatch/entity/service.py`): commit beb60cc4 added `[:1]` to `jpath.find(...)`, which dropped all but the first match. That broke wildcard paths like `asset[*].id`. I removed the slice, so `find_entities` returns every match again.

Both changes are uncommitted in the working tree. I didn't commit or push, since you didn't ask for that.

The perf goal of beb60cc4 is lost with this revert. If you still want it, the cut-off should apply only to paths that name a single field, not to wildcards.