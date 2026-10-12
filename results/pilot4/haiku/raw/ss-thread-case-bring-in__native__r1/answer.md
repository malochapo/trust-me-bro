The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. It only adds people to a thread when the case has a thread and its first linked signal's definition is in the `production` lifecycle.

- **Hand-opened cases:** No. The thread branch requires `case.signal_instances`, and a case opened by hand has none, so nobody is added to the thread. If the case has a dedicated channel instead, the person is added to the channel.
- **Alert-raised cases:** The alert's signal definition must have `lifecycle` set to `"production"`. The check reads `case.signal_instances[0].signal.lifecycle == "production"`, and `lifecycle` is a plain string column on the signal model (`src/dispatch/signal/models.py:139`). Any other value, including unset, means no one is added.

I changed nothing.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle set to "production" on the alert's signal definition