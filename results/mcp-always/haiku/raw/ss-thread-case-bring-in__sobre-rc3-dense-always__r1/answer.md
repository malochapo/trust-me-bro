The function is `add_case_participants`. It only adds people to a thread-based case when the case was raised by a production alert.

- **Who decides:** `add_case_participants` in `src/dispatch/conversation/flows.py:463`. It is called from `case_add_or_reactivate_participant_flow` in `src/dispatch/case/flows.py:135`, which runs when a person is added to a case.
- **Hand-opened cases:** No. The thread branch only runs when `case.signal_instances` is non-empty. A case opened by hand has no signal instances, so nothing is added to the thread.
- **Alert-raised cases:** The thread branch also checks `case.signal_instances[0].signal.lifecycle == "production"` (`conversation/flows.py:487`). Only alerts whose definition (the `Signal` model, `src/dispatch/signal/models.py:139`) has `lifecycle` set to `"production"` qualify. Other values, including `"active"`, are skipped. The participant is still added to the case itself; only the thread step is skipped.
- **Channel cases:** Cases with a real channel instead go through the `elif case.has_channel` branch, which adds the person to the channel directly and has no lifecycle check.

I did not change any code and did not run the tests.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle set to "production"