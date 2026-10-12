Only cases raised by a production signal get people added to the thread. Hand-opened cases do not, and no code was changed.

- **Function:** `add_case_participants` in `src/dispatch/conversation/flows.py:463`. `case_add_or_reactivate_participant_flow` in `src/dispatch/case/flows.py` calls it when a person is added to a case, and it is the function that adds them to the thread.
- **Hand-opened cases:** The thread branch only runs when `case.signal_instances` is non-empty. A case opened by hand has no signal instances, so nobody is brought into the thread.
- **Alert-raised cases:** The thread branch checks `case.signal_instances[0].signal.lifecycle == "production"`. The signal's `lifecycle` field is a string on the signal model (`src/dispatch/signal/models.py:139`). The alert's definition must therefore be marked `lifecycle` = `production`. The code checks only the first signal instance.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production