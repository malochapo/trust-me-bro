The function is `_should_update_signal_message`, and the minimum gap is 5 seconds.

It is called from `signal_instance_create_flow` (`src/dispatch/signal/flows.py:94`), but only when the repeat was deduplicated into an existing case that has a conversation. It returns True, and the alert's post is redrawn, only when all of these hold:

- `filter_action` is `deduplicate`.
- The case has a `signal_thread_ts`, so there is a thread to update.
- At least 5 seconds have passed between the current instance's `created_at` and the `created_at` cached for that case at the last redraw.

When the check passes, it updates the cache entry for the case, so the next gap is measured from that redraw. The first signal for a case always returns True and seeds the cache. The cache is a `TTLCache` with `maxsize=4` and `ttl=60`, so entries expire after 60 seconds, and a case can lose its entry and redraw sooner than the 5-second gap would otherwise allow. I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds