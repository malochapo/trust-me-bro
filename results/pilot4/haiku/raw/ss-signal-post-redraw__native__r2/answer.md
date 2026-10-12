The function is `_should_update_signal_message` in `src/dispatch/signal/flows.py`. It returns True only when the repeat was deduplicated into an existing case that already has a Slack thread (`signal_thread_ts`), and at least 5 seconds have passed since the last redraw for that case. The caller at lines 91–97 then invokes `update_signal_message`, which redraws the post.

The gap is measured between the signal instances' `created_at` timestamps, not wall-clock time. The last-redraw timestamp is kept in a `TTLCache(maxsize=4, ttl=60)` keyed by case ID. The first signal for a case always returns True, and that cache entry is what the 5-second check compares against.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds