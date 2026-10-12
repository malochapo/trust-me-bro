The function is `_should_update_signal_message`. It decides whether a deduplicated repeat triggers a redraw of the alert's post in the case's thread. The minimum gap is 5 seconds.

It's called from `signal_instance_create_flow` (`src/dispatch/signal/flows.py:94`). A repeat is redrawn only if it is a deduplicated instance on a case that has a conversation, and `_should_update_signal_message` returns True. That function then calls `update_signal_message`, which updates the post in the thread (`thread_id=case.signal_thread_ts`).

The gate works like this:
- The first time a case is seen, it records the time and returns True.
- Later, it returns True only if the instance is `SignalFilterAction.deduplicate`, the case has a `signal_thread_ts`, and at least 5 seconds have passed since the last recorded redraw (`timedelta(seconds=5)`).
- When it returns True, it stores the new timestamp. Repeats inside the 5-second window are skipped and do not reset the timer.
- The record lives in a `TTLCache(maxsize=4, ttl=60)`, so entries expire after 60 seconds and at most 4 cases are tracked.

No code was changed.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds