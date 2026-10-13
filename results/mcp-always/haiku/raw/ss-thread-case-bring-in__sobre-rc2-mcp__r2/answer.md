The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. It only adds people to a case thread when the case has a thread and its first signal instance comes from a signal whose lifecycle is `"production"` (lines 480-504).

- **Hand-opened cases:** No. A case opened by hand has no signal instances, so the `if case.signal_instances:` check fails and nobody is added to the thread. Cases with a dedicated channel and no thread take a separate `elif` branch that adds people to the channel, but that is not the thread case you asked about.
- **Alert-raised cases:** The alert's signal definition must have `lifecycle` set to `"production"`. Any other value, or no value, means no one is added. The string is only checked in this one place, and I did not find where lifecycle values are defined or validated.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production