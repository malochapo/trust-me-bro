`_should_update_signal_message` in `src/dispatch/signal/flows.py` (line 351) decides whether a repeat gets the post redrawn. I read the function but didn't check its caller. I'm assuming the repeat is a deduplicated signal instance in a case that already has a signal thread.

A repeat gets the redraw only if all of these hold:
- Its filter action is `deduplicate`.
- The case already has a `signal_thread_ts`.
- At least 5 seconds have passed since the last redraw for that case. The function measures this as the new instance's `created_at` minus the cached `created_at` of the last redraw.

The first instance seen for a case always returns True and records its timestamp. The cache is a `TTLCache` with a 60-second TTL, so a case's entry expires after 60 seconds. After that, the next repeat is treated as a first instance and gets a redraw regardless of the 5-second rule.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds