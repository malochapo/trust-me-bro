The function is `_should_update_signal_message`. It returns True only when a repeat is deduplicated, the case already has a `signal_thread_ts`, and at least 5 seconds have passed since the last redraw for that case.

The check runs in `signal_instance_create_flow` (`src/dispatch/signal/flows.py`, around line 89), but only for repeats that `filter_signal` has already deduplicated and whose case has a conversation. It then calls `update_signal_message`, which redraws the post.

The gap is measured between the `created_at` timestamps of signal instances, not wall-clock time. The last-redraw state lives in a process-local `TTLCache` (`_last_nonupdated_signal_cache`, maxsize 4, ttl 60s). Two consequences:
- The first repeat seen for a case always redraws, because there is no cache entry yet.
- A cache entry older than 60 seconds expires, so the next repeat also redraws.

I made no code changes. I also saved this as a finding in the sobre session.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds