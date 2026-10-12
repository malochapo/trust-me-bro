A person added to a thread case is brought in by `add_case_participants` in `src/dispatch/conversation/flows.py`. It decides this itself and then calls the Slack plugin's `add_to_thread` to do the adding.

- **Hand-opened cases:** No. For a thread case, `add_case_participants` only adds people when `case.signal_instances` is non-empty. A case opened by hand has no signal instances, so nobody is added to its thread and the function does nothing else.
- **Alert-raised cases:** The first signal instance's alert definition (`signal.lifecycle`) must equal `"production"`. The code comments that participants are only added to case threads that originate from signals in production.
- **Dedicated-channel cases:** These take a separate branch (`elif case.has_channel`), which adds people to the channel with no lifecycle check.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production