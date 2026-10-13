The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. It handles both channel cases and thread cases.

For a thread case (`case.has_thread`), it only calls `add_to_thread` when the case has signal instances. It then checks the first signal instance's signal and requires its `lifecycle` to be `"production"`. A case opened by hand has no signal instances, so nobody is brought into its thread. For a case with a channel of its own, participants are simply added to the channel.

An alert-raised case therefore needs its alert definition (the signal) to have `lifecycle == "production"`.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production