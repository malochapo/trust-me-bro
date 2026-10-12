The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. It checks `case.has_thread`, which is true when the case's conversation has a `thread_id`.

- **Hand-opened cases:** people are not brought into the thread. The thread branch only adds participants when `case.signal_instances` is non-empty. A case opened by hand has no signal instances, so the branch does nothing and no one is added.
- **Alert-raised cases:** the code checks `case.signal_instances[0].signal.lifecycle == "production"`. Only then does it call `plugin.instance.add_to_thread(...)` and log a participant-updated event. The code comment says participants are only added to threads for cases that come from signals in production.

Cases with their own channel go through a separate `elif case.has_channel` branch, which uses `plugin.instance.add(...)`.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production