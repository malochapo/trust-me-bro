When a person is added to a case that lives as a thread in a shared channel, `add_case_participants` decides whether they are brought into that thread. It is in `src/dispatch/conversation/flows.py`.

- **Thread cases:** The function only adds people when `case.has_thread` is true and the case has signal instances. A thread is the case where the conversation has a `thread_id`.
- **Opened by hand:** No, people are not brought into the thread. A case opened by hand has no `signal_instances`, so the inner check never passes and nothing happens.
- **Raised by an alert:** The function checks `case.signal_instances[0].signal.lifecycle == "production"`. Only then does it call `add_to_thread`. The code comment says the same: "we only add participants to case threads that originate from signals in production". So the alert's definition must have its lifecycle set to `"production"`.

I changed no code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production