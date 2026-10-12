The function is `_should_update_signal_message` in `src/dispatch/signal/flows.py`. It returns True, meaning the alert's post is redrawn, only when the repeat's filter action is `deduplicate`, the case has a `signal_thread_ts`, and at least 5 seconds have passed since the last redraw recorded for that case. The last-redraw time comes from an in-memory `TTLCache` keyed by case ID.

Two details that affect the gap in practice:
- The cache has a 60-second TTL and holds only 4 entries. If a case's entry has expired or been evicted, the next repeat is treated as a first sighting and redraws regardless of the 5-second rule.
- The gap is measured between the repeats' `created_at` timestamps, not the wall-clock time of the redraw.

I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds