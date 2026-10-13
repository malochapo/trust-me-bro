Hand-opened cases have no signal instances, so nothing is added.

The function is `add_case_participants` in `src/dispatch/conversation/flows.py:463`. It is called when a person is added to a case, including from `case_add_or_reactivate_participant_flow` in `case/flows.py`.

**Cases with a thread.** The function only brings someone into a thread when `case.has_thread` is true and `case.signal_instances` is non-empty. It then also requires `case.signal_instances[0].signal.lifecycle == "production"`. If any of those fail, it does nothing for that case: no one is added and no event is logged. A comment in the code says participants are only added to threads that originate from signals in production.

**Opened by hand.** No. A case opened by hand has no signal instances, so the `if case.signal_instances:` check fails and nobody is brought into the thread.

**Raised by an alert.** The alert's definition, which is the signal, must have its `lifecycle` set to `"production"`. Only the first signal instance on the case is checked.

**Cases with a dedicated channel.** The function takes a different branch (`elif case.has_channel`) and adds people to the channel with no lifecycle check.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production