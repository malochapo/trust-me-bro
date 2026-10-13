When a person is added to a case, `add_case_participants` decides whether they join the thread. It lives in `src/dispatch/conversation/flows.py` at line 463. The thread branch only runs when `case.has_thread` is true, and it adds the person only if `case.signal_instances[0].signal.lifecycle == "production"`.

- **Hand-opened cases:** No. A case opened by hand has no signal instances, so the thread branch never adds anyone. Those cases fall through to the `has_channel` branch, which is for cases without a thread. A hand-opened case that has a thread therefore gets no one added by this function.
- **Alert-raised cases:** The alert's definition must be marked with lifecycle `production`. Only the first signal instance is checked.

I did not run the code or any tests. This is from reading the code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle = "production" (on the alert's signal definition)