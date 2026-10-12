The function is `add_case_participants` in `src/dispatch/conversation/flows.py`.

- **Which function decides:** `add_case_participants` checks `case.has_thread` and, for thread cases, checks the case's signal instances before calling `plugin.instance.add_to_thread(...)`. If the case has a channel of its own, it calls `plugin.instance.add(...)` instead.
- **Opened by hand:** No. A hand-opened case has no `signal_instances`, so the inner `if case.signal_instances:` check fails. Nobody is added to the thread, and nothing is logged.
- **Raised by an alert:** The code checks `case.signal_instances[0].signal.lifecycle == "production"`. The first alert instance's signal definition must have its `lifecycle` set to `"production"`. The code comment says participants are only added to threads that come from production signals.

I didn't change any code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production