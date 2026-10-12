The function is `_should_update_signal_message`, and the minimum gap is 5 seconds.

It lives in `src/dispatch/signal/flows.py:351`. A repeat triggers a redraw of the alert post only when all of these hold:

- The signal instance's `filter_action` is `SignalFilterAction.deduplicate`.
- The case has a `signal_thread_ts`.
- At least 5 seconds have passed since the last cached redraw for that case. The gap is measured on `signal_instance.created_at`, not wall-clock time.

The last-redraw timestamps live in `_last_nonupdated_signal_cache`, a `TTLCache(maxsize=4, ttl=60)` at line 348. The first signal for a case always returns True and seeds the cache. Non-deduplicate repeats return False without touching the cache.

I didn't change any code. I did record this as a finding in the sobre session.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds