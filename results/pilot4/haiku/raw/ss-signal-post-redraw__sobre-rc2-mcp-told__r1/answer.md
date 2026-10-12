The function is `_should_update_signal_message`, defined in `src/dispatch/signal/flows.py`. It decides whether a repeat signal gets its alert post redrawn at the top of the case thread.

It only returns True for a repeat that is a deduplicate action, on a case that already has a signal thread timestamp, and at least 5 seconds after the last redraw for that case. The last-redraw time is kept per case in the module-level `_last_nonupdated_signal_cache`, and it is refreshed only when a redraw is approved. I read lines 351–380 directly; I did not read the rest of the function, which presumably returns False otherwise.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds