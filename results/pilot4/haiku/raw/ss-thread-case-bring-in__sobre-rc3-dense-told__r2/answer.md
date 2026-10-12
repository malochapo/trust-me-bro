The function is `add_case_participants`. It only adds people to a thread when the case was raised by an alert whose definition is marked production. Hand-opened cases are not brought in.

How it decides, in `src/dispatch/conversation/flows.py:463-524`:

- **Thread cases** (`case.has_thread`): people are added only if the case has signal instances and the first one's `signal.lifecycle == "production"`. Otherwise nothing is added to the thread.
- **Channel cases** (`case.has_channel`): people are added to the channel directly, with no lifecycle check.

`case_add_or_reactivate_participant_flow` in `src/dispatch/case/flows.py:81-160` calls this function when a person is added to a case, so that is the entry point for the question.

Hand-opened cases have no signal instances, so the thread branch never adds anyone. The alert's definition is the `Signal` model (`src/dispatch/signal/models.py`, the `lifecycle` column at line 139). Its `lifecycle` must be `"production"`. I did not check the allowed values of that column, but the code compares against exactly that string.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: "production"