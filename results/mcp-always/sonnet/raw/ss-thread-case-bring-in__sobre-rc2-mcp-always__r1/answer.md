A person added to a thread-based case is brought into the thread by `add_case_participants` in `src/dispatch/conversation/flows.py` (line 463). `case_add_or_reactivate_participant_flow` in `src/dispatch/case/flows.py` calls it, but the thread decision is made inside `add_case_participants`.

**Cases opened by hand:** no. For a case that lives in a thread (`case.has_thread`), the function only calls `add_to_thread` when the case has signal instances (`case.signal_instances`). A case opened by hand has none, so nobody is added to its thread and the function does nothing. The code comment gives the rule as "we only add participants to case threads that originate from signals in production."

**Cases raised by an alert:** the function checks the first signal instance's alert definition, `case.signal_instances[0].signal.lifecycle`. People are only brought in when that equals `"production"`. Any other lifecycle value skips the add.

I changed no code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production