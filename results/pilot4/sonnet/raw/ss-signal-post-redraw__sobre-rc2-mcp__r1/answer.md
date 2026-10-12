`_should_update_signal_message` in `src/dispatch/signal/flows.py` decides this. It is called at line 94, in the flow that folds a repeat into an existing case.

- **First repeat for a case:** the function returns `True` if the case has no entry in its in-memory cache. It then records that instance's `created_at`.
- **Later repeats:** the function returns `True` only if all three conditions hold:
  - the filter action is `deduplicate`;
  - the case already has a `signal_thread_ts`, meaning the alert's post exists in the thread;
  - the new instance's `created_at` is at least 5 seconds after the cached `created_at` for that case.
- **When it returns `True`:** the cached timestamp is updated, so the 5-second gap is measured from the last redraw. Otherwise it returns `False`.
- **Cache expiry:** the cache is a `TTLCache` with a 60-second TTL and `maxsize=4`. An entry that has gone 60 seconds without being refreshed expires, and the next repeat then counts as a first one and redraws. With only 4 slots, a case's entry can also be evicted early when other cases are active.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds