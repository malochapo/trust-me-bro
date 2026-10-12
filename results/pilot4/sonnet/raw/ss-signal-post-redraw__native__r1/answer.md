`_should_update_signal_message` decides it. It is defined in `src/dispatch/signal/flows.py:351` and called at line 94.

**How it decides:**
- It keeps a small in-memory cache, `_last_nonupdated_signal_cache`, keyed by case ID. Each entry stores the `created_at` of the last repeat that triggered a redraw. The cache is a `TTLCache` with `maxsize=4` and `ttl=60`, so an entry also expires after 60 seconds.
- If the case has no cache entry, it returns `True` and records the entry. The first repeat therefore always redraws.
- If there is an entry, a repeat redraws only if all three conditions hold:
  - its `filter_action` is `SignalFilterAction.deduplicate`;
  - the case has a `signal_thread_ts`, meaning the alert post already exists in the thread;
  - `signal_instance.created_at` is at least `timedelta(seconds=5)` after the cached `created_at`.
- When it returns `True` this way, it refreshes the cache entry. Otherwise it returns `False`.

The minimum gap is 5 seconds. The 60-second cache TTL also means that after a minute without a redraw, the entry is gone and the next repeat redraws regardless of the 5-second check.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds