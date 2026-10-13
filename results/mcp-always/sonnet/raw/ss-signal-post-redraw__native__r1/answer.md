`_should_update_signal_message` in `src/dispatch/signal/flows.py` (line 351) decides this. It is called from line 94, in the flow that handles repeats folded into an existing case. I didn't open `update_signal_message` itself, so I haven't confirmed it is the code that redraws the post.

The function uses a per-case cache keyed by case ID. The cache is a `TTLCache` with `maxsize=4` and `ttl=60`. Its logic is:

- **First repeat for a case (nothing cached):** it records the signal's `created_at` and returns True.
- **Later repeats:** it returns True only if all of these hold:
  - the filter action is `deduplicate`;
  - the case has a `signal_thread_ts`, meaning the alert post already exists in the thread;
  - at least 5 seconds have passed since the cached `created_at`. This is measured against the last time the function returned True for that case, not against any repeat in between.
- **Anything else:** it returns False.

The cache entries also expire after 60 seconds. Once an entry has expired, the next repeat counts as a first repeat and is allowed through regardless of the 5-second check. With `maxsize=4`, at most four cases are tracked at once, so a busy system can evict entries early and allow a redraw sooner than 5 seconds.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds