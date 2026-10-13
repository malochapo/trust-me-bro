`_should_update_signal_message` in `src/dispatch/signal/flows.py` (line 351) decides this. The caller at line 94 uses it to gate the call that updates the alert's post in the case thread.

The function behaves as follows:
- **First repeat for a case:** if the case has no entry in the in-memory cache `_last_nonupdated_signal_cache`, it records the repeat's `created_at` and returns `True`.
- **Later repeats:** it returns `True` only when all three conditions hold:
  - The repeat's filter action is `deduplicate`.
  - The case has a `signal_thread_ts`, meaning an alert post already exists in its thread.
  - At least `timedelta(seconds=5)` has passed since the `created_at` stored for that case. On `True`, it stores the new `created_at`.
- **Otherwise:** it returns `False`, and the post is not redrawn.

The cache is a `TTLCache(maxsize=4, ttl=60)`. An entry that is more than 60 seconds old has expired, so the next repeat takes the "first repeat" path and redraws regardless. The 5-second threshold is the minimum gap that matters for repeats arriving in quick succession. Because `maxsize=4`, only four cases are tracked at once.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds