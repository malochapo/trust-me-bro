The function is `add_case_participants` in `src/dispatch/conversation/flows.py`.

- **Which function decides:** For a case that lives as a thread (`case.has_thread`), it calls the conversation plugin's `add_to_thread` only if the case has signal instances. It then checks the lifecycle of the first one's signal definition. For a case with its own channel (`has_channel`), it adds people to that channel instead.
- **Opened by hand:** No. A hand-opened case has no `signal_instances`, so the inner check never passes and nobody is added to the thread. The code does nothing at that point and logs nothing.
- **Raised by an alert:** The alert's signal definition must have `lifecycle == "production"`. The code comment says participants are only added to case threads that originate from signals in production. Only the first signal instance is checked.

I made no code changes.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production