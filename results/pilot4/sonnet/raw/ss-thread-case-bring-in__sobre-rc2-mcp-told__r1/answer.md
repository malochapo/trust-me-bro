I found the function, `add_case_participants`. Its thread branch only adds people when the case has a signal instance whose signal lifecycle is "production".

**Which function decides:** `add_case_participants` in `src/dispatch/conversation/flows.py`. If the case has a thread (`case.has_thread`), it calls `plugin.instance.add_to_thread(...)` only when `case.signal_instances` is non-empty and `case.signal_instances[0].signal.lifecycle == "production"`.

**Opened by hand:** No. A case opened by hand has no signal instances, so the `if case.signal_instances:` check fails and nobody is added to the thread. The code does nothing in that case, with no log or event.

**Raised by an alert:** The alert's definition (the signal) must have its `lifecycle` set to `"production"`. The code only checks the first signal instance on the case. Signals in any other lifecycle state don't get people added to the thread.

Channel-based cases (`has_channel`) are handled in a separate branch that adds people with `plugin.instance.add` and has no lifecycle check.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production