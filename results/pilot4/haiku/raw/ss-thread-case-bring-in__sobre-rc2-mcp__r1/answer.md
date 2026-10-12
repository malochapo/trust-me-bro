The function that decides is `add_case_participants` in `src/dispatch/conversation/flows.py:463`. It only adds people to a thread when the case has a thread conversation, the case has signal instances, and the first signal's definition has `lifecycle == "production"` (line 487). Otherwise it does nothing for thread cases. The lower-level `add_users_to_conversation_thread` in the Slack plugin's `service.py` does the actual invite, but it performs no eligibility check.

- **Hand-opened cases:** not brought in. A hand-opened case has no signal instances, so the check fails and no one is added to the thread.
- **Alert-raised cases:** the alert's signal definition must have its `lifecycle` set to `production`. Any other value, or an unset value, means no one is added to the thread. Dedicated-channel cases take a different branch and are not affected by this check.

I did not run the code or any tests; this is from reading the source.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production