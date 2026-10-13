`_should_update_signal_message` decides whether a repeat gets the alert's post redrawn in the case thread. It's called from `src/dispatch/signal/flows.py:94`.

- **First repeat:** if the case has no entry in the cache, it returns True and records the time.
- **Later repeats:** a repeat only triggers a redraw if three things hold:
  - its filter action is `deduplicate`;
  - the case has a `signal_thread_ts`;
  - at least 5 seconds have passed since the cached time for that case.
- **Cache:** the entry is refreshed only when a redraw is allowed. It is a `TTLCache` with a 60-second TTL and `maxsize=4`, so an entry can also expire or be evicted early. After that, the next repeat counts as a first one and gets a redraw.

The 5-second gap comes from `timedelta(seconds=5)` in the function.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds