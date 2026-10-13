The function is `_should_update_signal_message`, defined in `src/dispatch/signal/flows.py` at line 351. It returns True, meaning redraw the alert's post at the top of the case thread, only when all of these hold:

- The repeat's `filter_action` is `SignalFilterAction.deduplicate`.
- The case has a `signal_thread_ts`.
- At least 5 seconds have passed since the last redraw for that case. The gap is measured from the `created_at` stored in `_last_nonupdated_signal_cache`, which is only refreshed when a redraw happens.

The first signal seen for a case always returns True. The cache has a 60-second TTL, so an entry older than that is treated as a first signal again and also returns True.

I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds