The function is `add_case_participants` in `src/dispatch/conversation/flows.py`.

- **Which function decides:** `add_case_participants`. If the case has a thread, it calls the Slack plugin's `add_to_thread` only when the case came from an alert whose definition is marked as production. If the case has its own channel instead, it adds people to the channel directly.
- **Cases opened by hand:** No. A hand-opened case has no alert instances, so the `if case.signal_instances:` check fails and nobody is added to the thread. The code does nothing in that case and logs nothing.
- **Cases raised by an alert:** The check reads the first alert instance, `case.signal_instances[0].signal.lifecycle`. People are added only if that value is `"production"`. A comment in the code says participants are only added to threads that originate from signals in production.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production