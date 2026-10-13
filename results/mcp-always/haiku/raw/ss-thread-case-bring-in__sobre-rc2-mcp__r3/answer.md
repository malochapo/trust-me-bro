The function is `add_case_participants`, in `src/dispatch/conversation/flows.py`. It decides whether a person is added to a case's thread.

**Hand-opened cases:** No. The thread branch only runs when `case.signal_instances` is non-empty. A case opened by hand has no signal instances, so nobody is added to its thread.

**Alert-raised cases:** The thread is only populated when the first signal instance's signal definition has `lifecycle == "production"`. Any other value, including `None`, means the person is not added. The lifecycle field is on the `Signal` model (`src/dispatch/signal/models.py:139`), which is the alert definition.

I did not change any code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle set to "production" on the alert's signal definition