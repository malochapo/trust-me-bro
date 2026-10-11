**Root cause:** commit `9dc24f46` changed how custom deduplication filter windows are read. Before it, `filter_dedup` treated `SignalFilter.window` as minutes. The commit made it treat the value as seconds, so a window of 120 now looks back 2 minutes instead of 2 hours. Signals arriving more than 2 minutes apart never match an open case, so each one creates a new case. Signals without a custom filter use the separate default-window path, which the commit left correct, so they are unaffected.

**Evidence:**
- `src/dispatch/signal/service.py:846-847` (`filter_dedup`): `window = _window_start(f.window)`, with the comment "SignalFilter.window is stored in seconds". `_window_start` (line 784) calls `timedelta(seconds=...)`.
- The pre-commit code was `window = datetime.now(timezone.utc) - timedelta(minutes=f.window)`.
- The only signal-related commit in the 2025-08-12 to 2025-08-16 range is `9dc24f46` ("refactor(signal): share the lookback window computation"). Its diff shows the unit change.
- The log has 48 "created case" and 48 "filtered: action=deduplicate" lines for GuardDuty on 08-14 and 08-15, while the other signals in the log dedupe normally.

**Caveats:**
- The log's first GuardDuty failure is at `2025-08-14T02:55:57Z`, but the commit is dated `2025-08-14 12:15 -0500` (17:15Z). Either the commit was deployed later than authored, or the timestamps don't line up. I did not reconcile this.
- The unit convention is inconsistent in the codebase. The model default is `60 * 60` with a comment saying seconds, and the UI offers window choices of 5, 10, 15, 20, and 30 with no unit label, which look like minutes. The "120" in the UI is consistent with minutes. The fix should restore minutes (`timedelta(minutes=f.window)`) or make the UI and model agree on seconds. I haven't changed any code.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The custom-filter branch passes the stored window (120, a minutes value from the UI) to `_window_start`, which treats it as seconds, shrinking the dedup lookback from 2 hours to 2 minutes so GuardDuty signals never match an open case.
INTRODUCED_BY: 9dc24f46