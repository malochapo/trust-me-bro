`_should_update_signal_message` decides this. It's in `src/dispatch/signal/flows.py:351`, and `signal_instance_create_flow` calls it at line 94.

A repeat can redraw the post only in these cases:
- **First repeat for the case:** the case has no entry in the per-case cache, so it returns true and records the time.
- **Later repeats:** all three of these must hold:
  - The repeat's filter action is `deduplicate`.
  - The case already has a `signal_thread_ts`, meaning the alert post exists in the thread.
  - The repeat's `created_at` is at least 5 seconds after the cached time of the last redraw for that case. The cache is then updated.

The cache is a `TTLCache` with a 60-second TTL. If a case's entry expires, the next repeat counts as a first one and redraws without any gap check. So 5 seconds is the minimum gap, and in practice a repeat arriving more than 60 seconds after the last redraw always triggers one.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds