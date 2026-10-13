The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. It handles thread cases differently depending on how the case was opened.

- **Hand-opened cases:** People are not brought into the thread. The thread branch only runs when `case.signal_instances` is non-empty, and a case opened by hand has no signal instances.
- **Alert-raised cases:** The case's first signal instance must reference a signal whose `lifecycle` is `"production"` (`src/dispatch/conversation/flows.py:487`). The signal model's `lifecycle` column is at `src/dispatch/signal/models.py:139`. Any other lifecycle value means the participant is not added to the thread.

Two side notes. The thread branch also requires `case.has_thread`, meaning the case has a conversation with a `thread_id`. Cases with a dedicated channel take the other branch and add people to the channel itself. I did not change any code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle set to "production"