`_should_update_signal_message` in `src/dispatch/signal/flows.py` (line 351) makes that decision. Its caller at line 94 uses it to gate the call that updates the alert's message in the case thread. I did not open the plugin's `update_signal_message` to confirm it deletes and reposts the post. I'm inferring "redraw" from the name and the call site.

- **First repeat for a case:** no cache entry exists, so it returns True and records the time.
- **Later repeats:** it returns True only if all of these hold:
  - the instance's filter action is `deduplicate`;
  - the case has a `signal_thread_ts`;
  - the instance's `created_at` is at least 5 seconds after the cached `created_at` for that case.
- **Cache expiry:** the cache is a `TTLCache` with a 60-second TTL. Once an entry expires, the next repeat counts as a first one and returns True regardless of the 5-second check.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds