The suite is green: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you asked. I didn't commit anything.

I found two real bugs. Only two tests were failing here, not failures across several packages as CI showed, so CI may have hit something I didn't reproduce.

1. **Entity extraction truncated wildcard JSONPaths** (`src/dispatch/entity/service.py`, around line 289). Commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]` to `jpath.find(...)`. A path like `asset[*].id` legitimately yields several values, so only the first was kept. I removed the slice and the comment that went with it. The perf goal of the commit is lost, but correctness requires all matches.

2. **Members could see every restricted case** (`src/dispatch/database/service.py`, `restricted_case_filter`, around line 835). The filter was `open OR restricted OR participant-email-matches`, so any restricted case was visible to a member, whether or not they were a participant. It is now `open OR (restricted AND participant-email-matches)`.

The commit `beb60cc4` is the likely source of one CI failure. I didn't check git history to confirm when the restricted-visibility clause was added.