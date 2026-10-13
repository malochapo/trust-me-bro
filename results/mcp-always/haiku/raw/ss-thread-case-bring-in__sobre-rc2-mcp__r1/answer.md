The function is `add_case_participants`, and it only adds people to a thread when the case came from a production alert. I read the code and didn't change anything.

- **Function:** `add_case_participants` in `src/dispatch/conversation/flows.py` (line 463). If the case has a thread, it calls `plugin.instance.add_to_thread(...)`, which adds the users to the thread.
- **Hand-opened cases:** No. The thread branch only runs when `case.signal_instances` is non-empty. A case opened by hand has no signal instances, so nobody is added to its thread. Those cases only get the channel branch, which adds people to the channel.
- **Alert-raised cases:** The thread branch also requires `case.signal_instances[0].signal.lifecycle == "production"`. So the alert's definition (the signal definition, `signal.lifecycle`, a plain string column at `src/dispatch/signal/models.py:139`) must be set to `production`. The code only checks this value. It doesn't enforce the set of allowed values anywhere I looked.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production