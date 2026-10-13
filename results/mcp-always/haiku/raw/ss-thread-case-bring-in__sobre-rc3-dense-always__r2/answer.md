The function is `add_case_participants`, in `src/dispatch/conversation/flows.py:463`. It only adds people to a thread when the case has a thread and its first signal instance has a signal definition with lifecycle `"production"` (lines 485–493). Cases opened by hand have no signal instances, so the thread branch never runs for them and nobody is added to the thread. The alert's definition must therefore have its lifecycle set to `production`. I read this from the code only and did not run anything.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle set to "production" on the signal definition