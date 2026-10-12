The function is `_should_update_signal_message`, and a repeat can trigger another redraw only if at least 5 seconds have passed since the last redraw for that case.

It lives in `src/dispatch/signal/flows.py:351`. It returns True only when all of these hold:
- The signal's `filter_action` is `SignalFilterAction.deduplicate`.
- The case has a `signal_thread_ts`.
- At least 5 seconds have elapsed since the timestamp cached for that case.

The timestamp is stored in a per-case `TTLCache` with `maxsize=4` and `ttl=60`, so the gap is only enforced while the cache entry lives. The first signal for a case always returns True, and each True return updates the cached timestamp. `update_signal_message` at line 329 calls the plugin only when this check passes.

I did not change any code. I also saved a finding to the sobre session.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds