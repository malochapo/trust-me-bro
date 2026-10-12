Adding a person to a case's shared-channel thread is decided by `add_case_participants` in `conversation/flows.py`. A hand-opened case is not brought in. An alert-raised case is only brought in when the alert's signal definition has its lifecycle set to `production`. I read the code and changed nothing.

How it works:
- The function only acts if the case already has a thread (`case.has_thread`, which is true when the case's conversation has a `thread_id`). Otherwise it falls through to the `elif case.has_channel` branch, which adds people to a dedicated channel instead.
- For a threaded case it checks `case.signal_instances`. If there are none, the case was opened by hand and nobody is added to the thread.
- If there is a signal instance, it checks `case.signal_instances[0].signal.lifecycle == "production"`. Only then does it call `plugin.instance.add_to_thread(...)`. Any other lifecycle value means no one is added.
- `lifecycle` is a column on the `Signal` class in `signal/models.py`, which is the alert definition.

The caller path is `case_add_or_reactivate_participant_flow` in `case/flows.py`, and `add_users_to_case` in the Slack plugin, both of which call `add_case_participants`.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production