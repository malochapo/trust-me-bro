The function is `add_case_participants`, and it only adds people to a thread when the case was raised by a production alert. Hand-opened cases are skipped. No code was changed.

- **Function:** `add_case_participants` in `src/dispatch/conversation/flows.py` (line 463). For a case with a thread, it calls `add_to_thread` only if `case.signal_instances` is non-empty and `case.signal_instances[0].signal.lifecycle == "production"`. Cases with a channel but no thread go through `plugin.instance.add` instead.
- **Hand-opened cases:** A case opened by hand has no signal instances, so the `if case.signal_instances:` check fails and nobody is added to the thread. Adding a person to such a case goes through `case_add_or_reactivate_participant_flow` in `src/dispatch/case/flows.py`, which calls this function.
- **Alert-raised cases:** The alert's signal definition must have `lifecycle` set to `"production"`. The `lifecycle` column is on the `Signal` model in `src/dispatch/signal/models.py` (line 139).

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: "production" (the signal definition's lifecycle must be set to production)