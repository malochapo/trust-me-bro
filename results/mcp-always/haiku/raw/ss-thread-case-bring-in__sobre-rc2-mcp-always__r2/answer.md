**Answer**

The function is `add_case_participants` in `src/dispatch/conversation/flows.py` (line 463). It adds participants to a case's thread only when the case has a thread and its first signal instance is from a production signal.

- **Hand-opened cases:** No. A case opened by hand has no signal instances, so the check `if case.signal_instances:` fails and nobody is added to the thread. The function also never reaches the `elif case.has_channel` branch, which covers dedicated channels, not threads.
- **Alert-raised cases:** The alert's definition must have its lifecycle set to `"production"`. The check is `case.signal_instances[0].signal.lifecycle == "production"` (line 487). I read the alert as the signal here, since the code keys on the signal's `lifecycle` column (`src/dispatch/signal/models.py:139`). Other lifecycle values, or a null lifecycle, mean the person is not brought into the thread.

I did not change any code. I didn't check the callers of this function, so I haven't confirmed that every "add person" path goes through it.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production