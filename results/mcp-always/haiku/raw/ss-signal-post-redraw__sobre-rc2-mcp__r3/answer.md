The function is `_should_update_signal_message`. It decides whether a deduplicated repeat triggers a redraw of the alert's post at the top of the case thread. A repeat must be at least 5 seconds after the last redraw for that case.

The check is in `src/dispatch/signal/flows.py:351`. It runs only when the repeat's filter action is `deduplicate` and the case has a `signal_thread_ts`. It compares the new instance's `created_at` with the cached time of the last redraw for that case, and returns True only when the gap is at least `timedelta(seconds=5)`. Two details matter:

- The first repeat for a case, with no cache entry, always returns True.
- The cache is a `TTLCache` with a 60-second TTL, so an entry older than that is dropped and the next repeat redraws again.

The caller is at `src/dispatch/signal/flows.py:94`, which also requires the case to have a conversation before calling `update_signal_message`.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds