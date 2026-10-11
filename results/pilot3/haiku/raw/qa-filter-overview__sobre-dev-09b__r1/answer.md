## How a new signal instance is classified

For a newly processed instance, Dispatch checks **snooze first, then deduplication, then case creation**. The entry point is `signal_instance_create_flow` in `src/dispatch/signal/flows.py`. It redacts the payload, runs `entity_service.find_entities` so the instance has entities, and then calls `signal_service.filter_signal`. `process_signal_batch` and `process_organization_signals` drive it for unprocessed instances (`filter_action` and `case_id` both null, oldest first, 500 per query).

`filter_signal` (`src/dispatch/signal/service.py`) runs in this order:

1. `filter_snooze`. If it sets `filter_action`, deduplication is skipped.
2. `filter_dedup`, only if nothing was snoozed.
3. If neither set `filter_action`, it is set to `none` and the instance is not filtered. Otherwise `filtered = True`. The session is committed.

Back in the flow, a filtered instance returns early. It may update the existing case's Slack signal message. An unfiltered instance continues: canaries return without a case, signals with `create_case` false return without a case, and everything else creates a case.

### 1. Snooze: `filter_snooze`

It iterates `signal.filters` and skips any filter that is not `mode == active` with `action == snooze`.

- **No expiration:** logs a warning and skips that filter, so it never snoozes.
- **Expired:** executes `break`, which ends the whole loop. Later snooze filters are not evaluated, not just this one.
- **Live:** builds a query over the same signal's `SignalInstance` rows, applies `apply_filter_specific_joins` and `apply_filters` with `f.expression`, and snoozes if the current instance's id is among the matches. An empty expression snoozes every instance of that signal.

Matching is on the expression only. There is no time window beyond the expiration. The matched fields depend on the expression and any joins that `apply_filter_specific_joins` adds. A snoozed instance gets `filter_action = snooze` and no case.

### 2. Deduplication: `filter_dedup`

- **Canary:** returns immediately. Canaries are never deduplicated.
- **Signal with no filters at all:** uses a default rule. The window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, where the config default is **45 minutes** (`src/dispatch/config.py:95`). It matches any other non-canary instance of the same signal with a non-null `case_id` created in the window, ignoring entities. It takes the most recent match's `case_id`. The `filter_signal` docstring says "1-hour"; that is stale.
- **Signal with filters:** only filters with `mode == active` and `action == deduplicate` are considered. For each one, in order, `filter_dedup` looks for non-canary instances of the same signal that:
  - match `f.expression` (with entity and entity-type joins),
  - were created within `f.window` seconds of now (`_window_start`),
  - share at least one entity with the current instance,
  - are not the current instance.

  It takes the earliest match and sets `case_id` to that match's case, with `filter_action = deduplicate`. Unlike the default path, this query does not require a non-null `case_id`, so it can copy a null `case_id` and still mark the instance as deduplicated.

If a signal has filters but none is an active deduplicate filter, no deduplication happens at all. The default rule applies only when `signal.filters` is empty.

Window units are seconds. `SignalFilter.window` is an `Integer` column with a default of 3600 (1 hour), and the `SignalFilterBase` schema defaults to 600 (10 minutes). I did not trace the API path that creates filters to see which default it uses.

### Canary signals

- `filter_dedup` skips canaries, and its queries exclude canary rows (`~SignalInstance.canary`), so canaries never match as dedup targets either.
- `filter_snooze` has no canary check, so a canary can be snoozed if a matching snooze filter exists.
- A canary that is not snoozed is stored with `filter_action = none` and no case. The flow comment calls this "limited support".

### Functions

- `signal_instance_create_flow`, `_should_update_signal_message`, `process_signal_batch`, `process_organization_signals`: `src/dispatch/signal/flows.py`
- `filter_signal`, `filter_snooze`, `filter_dedup`, `_window_start`, `get_unprocessed_signal_instance_ids`: `src/dispatch/signal/service.py`
- `apply_filters`, `apply_filter_specific_joins`: `src/dispatch/database/service.py`

I read the code but did not run the test suite.