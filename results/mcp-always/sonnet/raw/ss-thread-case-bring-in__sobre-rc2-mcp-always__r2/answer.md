Someone added to a thread-based case is brought into the thread by `add_case_participants` in `src/dispatch/conversation/flows.py` (line 463). I read this from the code and didn't run anything or change any code.

- **Opened by hand:** No. The thread branch (line 485) only acts when `case.signal_instances` is non-empty. A case opened by hand has no signal instances, so nothing happens. Participants are not added to the thread and no event is logged.
- **Raised by an alert:** The code checks `case.signal_instances[0].signal.lifecycle == "production"`. The alert's definition (the signal) must have its lifecycle set to `"production"`. The code comment says participants are only added to case threads that originate from production signals. Only the first signal instance is checked.

The `elif case.has_channel` branch is separate. It adds people to a case that has its own channel, regardless of how the case was opened.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production