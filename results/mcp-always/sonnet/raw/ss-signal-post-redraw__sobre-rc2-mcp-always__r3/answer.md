`_should_update_signal_message` decides this. It is defined in `src/dispatch/signal/flows.py:351` and called from line 94 of the same file.

- **First repeat for a case:** if the case has no entry in the cache, the function returns `True`, so the post is redrawn. It then records that signal's `created_at`.
- **Later repeats:** the function returns `True` only when three things hold. The signal's `filter_action` must be `deduplicate`, the case must have a `signal_thread_ts`, and the signal's `created_at` must be at least 5 seconds after the cached `created_at`. A redraw refreshes the cached timestamp, and a suppressed repeat leaves it as it was.
- **Cache lifetime:** the per-case cache is a `TTLCache` with a 60-second TTL and a `maxsize` of 4. A case's entry expires after 60 seconds. The next repeat then counts as a first one and gets redrawn regardless of the 5-second gap.

The gap is measured between the `created_at` timestamps of the two signals, not wall-clock time at the point of the check. I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds