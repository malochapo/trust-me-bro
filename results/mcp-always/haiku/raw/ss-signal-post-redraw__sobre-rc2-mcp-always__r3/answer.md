The function is `_should_update_signal_message`, and the minimum gap between redraws for the same case is 5 seconds.

It sits in `src/dispatch/signal/flows.py:351`. It is called from `signal_instance_create_flow` (`flows.py:94`) only when a repeat was deduplicated into an existing case that has a conversation. It returns True, and the Slack alert post is redrawn, only if all of these hold:

- `filter_action` is `deduplicate`.
- The case has a `signal_thread_ts`.
- At least 5 seconds have passed between the repeat's `created_at` and the `created_at` of the last redraw recorded for that case.

A repeat that arrives in a case with no cache entry yet always redraws and starts the timer. The last-redraw record lives in an in-process `TTLCache` (`flows.py:319`, maxsize 4, TTL 60 seconds), so an entry older than 60 seconds expires and the next repeat redraws regardless of the 5-second gap.

I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds