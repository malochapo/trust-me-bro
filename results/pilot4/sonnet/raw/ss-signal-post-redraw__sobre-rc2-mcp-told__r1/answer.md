`_should_update_signal_message` in `src/dispatch/signal/flows.py` (line 351) decides this. Its only caller is at line 94, in the same file.

How it decides, per case ID:
- **First repeat:** the first time the function sees a case, it records the signal's `created_at` and filter action in a small cache and returns True. That repeat gets the post redrawn.
- **Later repeats:** it returns True only when three things all hold. The signal's filter action is `deduplicate`, the case has a `signal_thread_ts`, and at least 5 seconds have passed between this signal's `created_at` and the `created_at` stored for the last redraw. On True it stores the new `created_at`.
- **Otherwise:** it returns False and the post is not redrawn.

The cache is a `TTLCache` with `maxsize=4` and `ttl=60`. It holds at most 4 cases, and each entry expires after 60 seconds. After an entry expires, or is evicted to make room, the next repeat for that case counts as a first repeat and is redrawn regardless of the 5-second gap.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds