The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. A person is brought into a shared-channel thread only if the case has a signal, and that signal's definition is marked `production`.

- **Hand-opened cases:** No. The thread branch only proceeds when `case.signal_instances` is non-empty. A case opened by hand has no signal instances, so nobody is added to its thread. (Hand-opened cases with a dedicated channel take the separate `has_channel` branch and are added to the channel.)
- **Alert-raised cases:** The alert's signal definition must have `lifecycle == "production"`. Any other lifecycle value, or no signal, means the person is not added. The check is on the first signal instance only (`signal_instances[0]`). I found no enum defining the lifecycle values, so the `"production"` string is the only evidence for this value.

I did not change any code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle = "production"