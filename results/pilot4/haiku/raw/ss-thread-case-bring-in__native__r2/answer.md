The function is `add_case_participants`, in `src/dispatch/conversation/flows.py`. It takes the case and the emails being added, and for a case with a thread (`case.has_thread`) it calls `plugin.instance.add_to_thread(...)` only when the case has signal instances and the first one's signal has `lifecycle == "production"`.

- **Hand-opened cases:** No. A case opened by hand has no signal instances, so the thread branch never adds anyone. Those people are not brought into the thread.
- **Alert-raised cases:** The alert's definition (the signal definition, `signal.lifecycle`) must be marked `production`. The `lifecycle` column is a free-form string (`src/dispatch/signal/models.py:139`), and `"production"` is the only value this check looks for, so I did not find a formal enum for it.

I changed no code.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production