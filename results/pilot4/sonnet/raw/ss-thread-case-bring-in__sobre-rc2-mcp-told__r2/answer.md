The function is `add_case_participants` in `src/dispatch/conversation/flows.py`.

For a case that lives as a thread (`case.has_thread`), it only calls `add_to_thread` when the case has signal instances and the first one's signal has `lifecycle == "production"`.

- **Opened by hand:** a case opened by hand has no signal instances, so nobody is brought into its thread. The function does nothing in that branch.
- **Raised by an alert:** the alert's signal definition must have its lifecycle set to `"production"`.

I only read the code and changed nothing.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production