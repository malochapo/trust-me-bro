`_should_update_signal_message` decides whether a repeat gets the alert post redrawn. It is called at `src/dispatch/signal/flows.py:94`.

- **First repeat for a case:** if there is no cache entry for the case, the function records the repeat's `created_at` and returns True.
- **Later repeats:** the function returns True only when all three conditions hold:
  - The repeat's filter action is `deduplicate`.
  - The case has a `signal_thread_ts`, meaning the alert already has a post in the thread.
  - At least 5 seconds have passed since the last redraw. This is measured from `created_at` of the last redraw, using the repeat's own `created_at`, not the current clock.
- **Otherwise:** it returns False.
- **Cache expiry:** the cache is a `TTLCache` with a 60-second TTL, so a case's entry disappears after 60 seconds. The next repeat then counts as a first one and is redrawn regardless of the 5-second rule.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds