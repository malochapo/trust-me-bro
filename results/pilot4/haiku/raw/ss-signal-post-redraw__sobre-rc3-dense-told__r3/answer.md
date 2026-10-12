The function is `_should_update_signal_message`, and the minimum gap is 5 seconds. I did not change any code.

It is defined at `src/dispatch/signal/flows.py:351-382`. For a repeat to redraw the alert post, all of these must hold:

- The repeat's filter action is `deduplicate`.
- The case has a `signal_thread_ts`.
- At least 5 seconds have passed between the repeat's `created_at` and the `created_at` stored at the last redraw for that case. The gap is measured from the last redraw, not the last repeat.

The first signal for a case always redraws. The per-case cache is a `TTLCache` with `ttl=60` (`flows.py:348`), so an entry expires after 60 seconds, and the next repeat after that redraws again.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds