signal_instance_create_flow only refreshes the signal message of a deduplicated instance when _should_update_signal_message returns True. That function keeps a TTLCache (maxsize 4, ttl 60 s) keyed by case id: the first filtered instance of a case triggers a redraw; later ones only if their filter action is deduplicate, the case has a signal thread, and their created_at is at least timedelta(seconds=5) after the instance that last triggered one.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds
