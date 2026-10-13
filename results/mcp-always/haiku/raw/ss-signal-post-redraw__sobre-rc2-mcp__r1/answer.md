The function is `_should_update_signal_message`, defined in `src/dispatch/signal/flows.py`. It decides whether a deduplicated repeat triggers `update_signal_message`, which redraws the alert's post in the case thread.

A repeat is redrawn only if all of these hold:
- The signal instance's `filter_action` is `deduplicate`.
- The case has a `signal_thread_ts`.
- At least 5 seconds have passed since the last redraw for that case, measured from `created_at` on the signal instances.

The first repeat for a case always redraws, because nothing is cached yet. The cache (`_last_nonupdated_signal_cache`) is a TTL cache with a 60-second TTL, so an entry older than that is dropped and the next repeat redraws again.

I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds