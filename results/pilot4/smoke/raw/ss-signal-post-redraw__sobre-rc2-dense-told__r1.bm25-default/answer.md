The function is `_should_update_signal_message`, and the minimum gap is 5 seconds.

In Dispatch, the repeating alerts are modeled as signals. A repeat folded into an open case gets its post redrawn in the case's Slack thread only if all of these hold (`src/dispatch/signal/flows.py:351-381`):

- The signal's `filter_action` is `deduplicate`.
- The case has a `signal_thread_ts`, so a thread exists.
- At least 5 seconds (`timedelta(seconds=5)`) have passed since the last redraw for that case.

The first signal for a case always redraws. The per-case timestamp is stored in `_last_nonupdated_signal_cache`, a `TTLCache` with a 60-second TTL. It is only updated when a redraw happens, so the 5-second gap is measured from the last redraw, not from the last repeat. Repeats inside that window are skipped.

I searched semantically first and got the signal function as the top relevant match. I did not change any code. I also recorded this as a finding in the sobre session.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds