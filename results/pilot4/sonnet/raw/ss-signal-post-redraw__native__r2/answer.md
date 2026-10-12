`_should_update_signal_message` in `src/dispatch/signal/flows.py` decides this. It's called at line 94 of that file, and the redraw it gates goes through `plugin.instance.update_signal_message`.

The function keeps a small in-memory cache, keyed by case ID, that records when each case last had its post redrawn.

- **First repeat for a case:** if the case has no cache entry, the function records it and returns True, so the post is redrawn.
- **Later repeats:** the function returns True only when all three of these hold:
  - the signal's filter action is `deduplicate`;
  - the case has a `signal_thread_ts`, meaning it already has a thread post;
  - at least 5 seconds have passed between this signal instance's `created_at` and the cached `created_at` from the last redraw.

  When it returns True it also refreshes the cache entry. Otherwise it returns False and the post is left alone.

The cache is a `TTLCache` with `maxsize=4` and a 60-second TTL. A case's entry therefore expires after 60 seconds, and with only four slots it can be evicted sooner when other cases are active. In either situation the next repeat counts as a first one and is redrawn immediately. I read the code and did not run it.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds