When a person is added to a case, `add_case_participants` in `src/dispatch/conversation/flows.py` decides whether they are brought into the thread.

- **Hand-opened cases:** No. The thread branch only runs when the case has a `signal_instances` entry. A case opened by hand has none, so nobody is added to its thread. Such a case is only handled by the `elif case.has_channel` branch, which adds people to the channel.
- **Alert-raised cases:** The alert's definition, the `Signal` model in `src/dispatch/signal/models.py`, must have its `lifecycle` set to `"production"`. The code checks `case.signal_instances[0].signal.lifecycle == "production"`, and only then calls `add_to_thread`. Any other lifecycle value, or no value, means the thread is left alone.

The code also requires `case.has_thread` to be true, meaning the conversation has a `thread_id`. I did not check the full set of lifecycle values, so `"production"` is taken from the comparison in this function rather than from a documented enum.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle = "production"