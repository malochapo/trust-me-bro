The function is `_should_update_signal_message` in `src/dispatch/signal/flows.py`. It decides whether a repeat gets the signal message redrawn. A repeat triggers a redraw only when at least 5 seconds have passed since the last redraw for that case.

It is called from `signal_instance_create_flow` (`flows.py:94`). The redraw happens only if the signal instance's filter action is `deduplicate`, the case has a `signal_thread_ts`, and the case already has a conversation. The first signal for a case always redraws, since nothing is cached yet. The last-redraw timestamp is held in a `TTLCache` (`maxsize=4`, `ttl=60`), so an entry expires after 60 seconds and the next repeat then redraws again. I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds