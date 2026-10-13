A person is brought into a case thread by `add_case_participants`, in `src/dispatch/conversation/flows.py`. It is called from `case_add_or_reactivate_participant_flow` in `src/dispatch/case/flows.py` when a participant is added.

It only adds people to the thread when the case has a thread (`case.has_thread`) and it has at least one signal instance. The first signal's definition must have `lifecycle == "production"`. Any other case gets no thread add, and the code logs nothing for it.

- **Hand-opened cases:** No signal instances exist, so people are not brought into the thread.
- **Alert-raised cases:** The alert's signal definition must have its lifecycle set to `production`. The code compares the value as a plain string, and the model defines `lifecycle` as a free-form `String` (`src/dispatch/signal/models.py:139`).

I did not change any code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle set to "production"