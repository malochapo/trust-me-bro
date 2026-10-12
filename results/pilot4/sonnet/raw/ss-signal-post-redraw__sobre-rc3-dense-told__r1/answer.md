The function is `_should_update_signal_message` in `src/dispatch/signal/flows.py`. It's called at line 94 of the same file. I read the code but didn't run it.

**How it decides**
- It keeps a small in-memory cache keyed by case ID. The cache is a `TTLCache` with `maxsize=4` and `ttl=60`, so entries expire after 60 seconds.
- The first repeat for a case, or the first after the cache entry has expired, is always allowed to redraw the post.
- Any other repeat is allowed only if all of these hold:
  - its filter action is `deduplicate`;
  - the case has a `signal_thread_ts`, meaning the post already exists in the thread;
  - at least 5 seconds have passed since the cached time, which is the previous allowed redraw for that case. It compares the repeat's `created_at` against the `created_at` stored in the cache.
- When a repeat is allowed, the cached time is updated. A repeat that is refused leaves it unchanged.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds