The function is `_should_update_signal_message` in `src/dispatch/signal/flows.py`, starting at line 351. A repeat triggers a redraw only when all three conditions hold:

- The signal instance's filter action is `deduplicate`.
- The case has a `signal_thread_ts`, so there is a thread to update.
- At least 5 seconds have passed since the last redraw for that case. The gap is measured from the cached `created_at` of the last update, and the cache is updated only when a redraw happens.

The first signal for a case always returns True, and the case's entry lives in a `TTLCache` with a 60-second TTL. I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds