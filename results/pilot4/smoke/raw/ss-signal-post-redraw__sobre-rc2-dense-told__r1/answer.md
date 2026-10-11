The function is `_should_update_signal_message`, and the minimum gap is 5 seconds.

In Dispatch, alerts arrive as signals, so the "alert post" is the signal message pinned at the case's `signal_thread_ts`. The function, in `src/dispatch/signal/flows.py` (lines 351–382), decides whether a repeat gets that post redrawn:

- The first signal for a case always redraws (the cache is empty).
- For later signals, a redraw happens only if the filter action is `deduplicate`, the case has a `signal_thread_ts`, and `signal_instance.created_at` is at least 5 seconds after the cached `created_at` for that case. The cache is updated only when a redraw happens, so the gap is measured from the last redraw.
- The `TTLCache(maxsize=4, ttl=60)` controls cache eviction, not the gap.

I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds