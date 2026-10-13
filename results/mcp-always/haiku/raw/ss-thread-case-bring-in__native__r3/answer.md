Adding someone to a case thread is decided by `add_case_participants` in `src/dispatch/conversation/flows.py`. Hand-opened cases are not brought in. For an alert-raised case, the alert's definition must have its lifecycle set to `production`.

The function only acts when `case.has_thread` is true. It then checks `case.signal_instances`. A case opened by hand has no signal instances, so the people are not added to the thread. For a case with signal instances, it only calls `add_to_thread` when the first instance's `signal.lifecycle` equals `"production"`. Any other lifecycle value, or no lifecycle, means nobody is added. The `lifecycle` column is on `Signal` in `src/dispatch/signal/models.py:139`, which is the alert definition. The check does not look at the `SignalInstance`.

When people are added, `add_to_thread` in the Slack plugin invites them to the channel and posts an "Adding the following individuals" message in the thread. Cases that live in a dedicated channel take a separate branch and are not affected by this rule.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: lifecycle set to "production" on the alert (signal) definition