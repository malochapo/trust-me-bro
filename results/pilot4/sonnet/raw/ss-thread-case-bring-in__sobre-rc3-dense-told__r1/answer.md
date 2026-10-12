The function that decides this is `add_case_participants`, in `src/dispatch/conversation/flows.py`. Case participants are added through `case_add_or_reactivate_participant_flow` in `src/dispatch/case/flows.py`, which calls it.

- **Thread cases:** `add_case_participants` only adds people to a thread when `case.has_thread` is true and the case has signal instances. A case opened by hand has no signal instances, so nobody is added to its thread.
- **Alert-raised cases:** people are added only if the first signal instance's alert definition (`signal.lifecycle`) is `"production"`. The code comment says this: "we only add participants to case threads that originate from signals in production".
- **Cases with their own channel:** these take the `elif case.has_channel` branch, which adds people without any signal check.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production