The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. It decides whether a person is brought into a case's thread, and it only does so when the case has a thread and its first signal is in production.

- **Hand-opened cases:** No. The thread branch requires `case.signal_instances` to be non-empty. A case opened by hand has no signal, so nobody is added to its thread. Those cases only get the channel-add branch when they have a dedicated channel.
- **Alert-raised cases:** The alert's signal definition must have `lifecycle` set to `"production"`. The code checks `case.signal_instances[0].signal.lifecycle == "production"`, and the field is `lifecycle` on the signal model (`src/dispatch/signal/models.py:139`).

Nothing in the repo was changed.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle = "production"