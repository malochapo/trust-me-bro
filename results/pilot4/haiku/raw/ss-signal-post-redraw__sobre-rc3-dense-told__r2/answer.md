The function is `_should_update_signal_message`, and the gap is 5 seconds.

It is called from `signal_instance_create_flow` (`src/dispatch/signal/flows.py:94`). When a repeat is deduplicated into an open case that has a conversation, it calls `update_signal_message` to redraw the signal's post in the case thread, but only if `_should_update_signal_message` returns true.

The function returns true in two cases:
- **First signal for a case:** if the case has no entry in `_last_nonupdated_signal_cache`, it caches the current timestamp and returns true.
- **Later repeats:** it returns true only when the filter action is `deduplicate`, the case has a `signal_thread_ts`, and at least 5 seconds have passed since the cached `created_at`. Only then does it refresh the cache.

Any repeat that arrives less than 5 seconds after the last redraw returns false and leaves the cache untouched.

I did not change any code. This answer is based on a semantic search plus reading `signal/flows.py`. I did not check the `update_signal_message` internals or the Slack side. I first looked for an alert-specific redraw path in the Slack plugin and found none, so I took the signal path as the intended one.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds