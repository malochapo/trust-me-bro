The function is `_should_update_signal_message`, and the minimum gap is 5 seconds.

It is called from `signal_instance_create_flow` in `src/dispatch/signal/flows.py` (around line 94). That call only runs when a repeat signal was deduplicated into an existing case that has a conversation. `_should_update_signal_message` returns true only when all of these hold:

- The signal's `filter_action` is `deduplicate`.
- The case has a `signal_thread_ts`, so there is a post to redraw.
- At least 5 seconds have passed since the cached `created_at` for that case. The cache is a `TTLCache` keyed by case ID, so the gap is measured from the last update that was allowed through.

If a case has no cache entry yet, the first repeat always returns true. A repeat inside the 5-second window is skipped. The 60-second TTL on the cache only controls how long an entry is kept, not the gap.

No code was changed.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds