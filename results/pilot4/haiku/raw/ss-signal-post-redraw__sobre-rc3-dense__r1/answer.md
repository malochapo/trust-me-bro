The function is `_should_update_signal_message` in `src/dispatch/signal/flows.py`. It decides whether a repeat gets its signal message redrawn, and it is called from the signal-instance create flow (line 94). It only returns True when the repeat's filter action is `deduplicate`, the case has a `signal_thread_ts`, and at least 5 seconds have passed since the last redraw for that case.

Two details to be aware of:
- The 5-second gap is measured from the `created_at` of the last signal that triggered a redraw, which is cached per case in a `TTLCache` (maxsize 4, ttl 60 seconds). If a case's cache entry expires, the next repeat redraws immediately.
- The first signal seen for a case that isn't in the cache always returns True.

I didn't change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds