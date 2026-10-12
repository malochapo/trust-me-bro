The function is `_should_update_signal_message`. It returns True only for a deduplicated repeat, and only when at least 5 seconds have passed since the last redraw for that case.

It is called at `src/dispatch/signal/flows.py:94`, which then calls `update_signal_message` to redraw the post. The check passes only when all of these hold:

- The signal's `filter_action` is `deduplicate`.
- The case has a `signal_thread_ts`.
- The time since the last cached update for that case is at least `timedelta(seconds=5)`.

The last-update timestamps live in `_last_nonupdated_signal_cache`, a `TTLCache` with `maxsize=4` and `ttl=60`. This means the gap is tracked in process memory, not in the database. Each case's first signal always triggers a redraw. I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds