The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. It handles adding people to a case's conversation.

- **Thread cases:** if the case has a thread (`case.has_thread`), it only calls `plugin.instance.add_to_thread(...)` when the case has signal instances. It also requires the first signal instance's signal to have `lifecycle == "production"`.
- **Hand-opened cases:** a case opened by hand has no signal instances, so nothing is added to the thread. The code skips it silently.
- **Alert-raised cases:** the alert's definition (the signal) must have its lifecycle set to `"production"`. Otherwise people are not brought into the thread.
- **Channel cases:** a case with its own channel takes a separate branch (`case.has_channel`) and uses `plugin.instance.add(...)`.

I made no code changes.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production