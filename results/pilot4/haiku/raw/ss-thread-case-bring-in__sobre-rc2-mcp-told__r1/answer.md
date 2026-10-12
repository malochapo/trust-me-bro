The function is `add_case_participants`, in `src/dispatch/conversation/flows.py`. It is called from `case_add_or_reactivate_participant_flow` in `src/dispatch/case/flows.py`, which runs when someone is added to a case.

For a case with a thread (`case.has_thread`), the person is added to the thread only if the case has signal instances and the first one's signal has `lifecycle == "production"`. A case opened by hand has no signal instances, so it fails that check and nobody is added to the thread. The `lifecycle` field is a free-form string on the signal definition (`src/dispatch/signal/models.py:139`), and the code compares it against `"production"`. Cases with a dedicated channel take a different branch (`add` to the channel) and are not affected by this check.

I did not run the code or its tests; this is from reading the source.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production