The function is `add_case_participants`. It decides whether a person is added to a case thread, and it only adds them when the case came from a production signal.

The thread branch (`case.has_thread`, `src/dispatch/conversation/flows.py:485`) adds participants only if two conditions hold:
- `case.signal_instances` is non-empty, so the case was raised by an alert.
- The first signal's `lifecycle` equals `"production"` (line 487).

A case opened by hand has no signal instances, so nobody is brought into its thread. A case raised by an alert needs its alert definition (the signal) marked with lifecycle `production`. Cases with a dedicated channel take a separate branch (`plugin.instance.add`) and are not affected by this gate.

I did not change any code. I recorded this as a finding in the sobre session.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production