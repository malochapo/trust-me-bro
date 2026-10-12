The function is `add_case_participants` in `src/dispatch/conversation/flows.py`. It is called from `case_add_or_reactivate_participant_flow` in `src/dispatch/case/flows.py`, which hands off to it when a person is added to a case. I did not change any code.

**Hand-opened cases:** No. The thread branch only runs when `case.signal_instances` is non-empty. A case opened by hand has no signal instances, so nobody is added to its thread.

**Alert-raised cases:** The alert's signal definition must have `lifecycle` set to `"production"`. The check reads `case.signal_instances[0].signal.lifecycle` and only calls `plugin.instance.add_to_thread(...)` when it equals `"production"`. The `lifecycle` column is defined on the signal model in `src/dispatch/signal/models.py`. Other lifecycle values are not added to the thread.

Two conditions also apply: the case must have a thread (`has_thread`, which means a conversation with a `thread_id`), and the case must not be closed.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle = "production"