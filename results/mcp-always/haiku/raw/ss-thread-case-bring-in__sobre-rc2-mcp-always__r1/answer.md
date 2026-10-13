The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. It brings people into a thread only when the case was raised by an alert whose definition is marked production. Cases opened by hand are not brought in.

- **Which function:** `add_case_participants` (`src/dispatch/conversation/flows.py:463`). For a case with a thread (`case.has_thread`), it calls `plugin.instance.add_to_thread(...)` only inside `if case.signal_instances:` and `if case.signal_instances[0].signal.lifecycle == "production":` (lines 486–487). Otherwise it does nothing for threads. Cases with a dedicated channel take the `elif case.has_channel` branch and are added to the channel instead.
- **Hand-opened cases:** No. A case opened by hand has no `signal_instances`, so the thread branch never adds anyone.
- **Alert-raised cases:** The alert's definition, stored as the `Signal` model (`src/dispatch/signal/models.py:139`, `lifecycle` column), must have `lifecycle` set to `"production"`. The `lifecycle` value comes from the signal definition, and the check reads it through `case.signal_instances[0].signal.lifecycle`. I did not confirm the exact allowed values beyond the `"production"` string checked in the code.

I did not change any code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle = "production"