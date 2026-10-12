The function is `add_case_participants`, in `src/dispatch/conversation/flows.py`.

- **How it decides:** it only brings people into a thread when the case `has_thread` and has `signal_instances`. It then checks that the first signal instance's signal has `lifecycle == "production"`.
- **Hand-opened cases:** these have no `signal_instances`, so nobody is added to the thread. The thread branch does nothing for them.
- **Alert-raised cases:** the alert's definition (the signal) must have its lifecycle marked `"production"`. In this code that is a `lifecycle` field on the signal, and the check reads it from the case's first signal instance.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production