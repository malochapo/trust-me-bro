## How a new signal instance is classified

I read this from the code without running it. The entry point is `signal_instance_create_flow` in `src/dispatch/signal/flows.py`. Unprocessed instances are picked up by `get_unprocessed_signal_instance_ids` (`signal/service.py`), which selects rows with `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500. They are run through `process_signal_batch` and `process_organization_signals`. I did not read `main_processing_loop` in full. The only detail I checked there is `LOOP_DELAY = 60` seconds.

### Order of operations in `signal_instance_create_flow`

1. Load the instance and redact `raw`.
2. Find entities. Entity types come from the signal plus those with `all` scope, via `entity_service.find_entities`. Entities are attached and committed before any filtering, so dedup can match on them.
3. Call `filter_signal`, which runs in this order:
   - `filter_snooze`. Runs first, for any instance, canary or not.
   - `filter_dedup`. Runs only if snooze did not set `filter_action`.
   - If neither matched, `filter_action` is set to `none`. Otherwise `filtered = True`. The result is committed.
4. If filtered, the function returns. If the instance has a case with a conversation and `_should_update_signal_message` says so, the Slack signal message is refreshed. No case is created.
5. If the instance is a canary, it returns here (see below).
6. If `signal.create_case` is false, it returns.
7. Otherwise it creates a case with `case_service.create`, sets `signal_instance.case`, and calls `case_flows.case_new_create_flow`. Then it runs `engage_signal_identity` (if the signal has engagements and entities) and the signal's workflows.

### Snooze: `filter_snooze`

- It iterates `signal.filters` in list order. It skips any filter whose `mode` is not `active` or whose `action` is not `snooze`.
- A snooze filter with no `expiration` logs a warning and is skipped.
- If `expiration` is in the past, the loop does `break`, not `continue`. Snooze evaluation stops there, so later snooze filters are not checked. Dedup still runs.
- If there is an `expression`, it is applied with `apply_filter_specific_joins` and `apply_filters` to all instances of the same signal. The snooze matches if the current instance is in that result. The query has no time window.
- If there is no `expression`, every instance of the signal is snoozed until expiration.
- A match sets `filter_action = snooze` and stops the loop.

Snooze has no time window. The only time value is the absolute `expiration` timestamp.

### Deduplication: `filter_dedup`

It has two branches, and the choice depends on whether the signal has any filters at all.

**Branch A: the signal has no filters (any mode or action).**
- Window: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. The default is 45 minutes (`src/dispatch/config.py:95`).
- Match: any other instance of the same signal, created in the window, with a non-null `case_id`, that is not a canary. Entities are not compared.
- Ordering: the most recent match is used (`order_by created_at desc`). Its `case_id` is copied and `filter_action = deduplicate` is set.

**Branch B: the signal has at least one filter.** Only filters with `mode == active` and `action == deduplicate` are considered, in list order. The first match wins.
- Window: `f.window`, in seconds, looked back from now.
- Match: other instances of the same signal, created in the window, not canary, that share at least one entity ID with the current instance and satisfy `f.expression`. The expression is applied with `apply_filters` after joining entities and entity types.
- Ordering: the earliest matching instance (`order_by created_at asc`). Its `case_id` is copied and `filter_action = deduplicate` is set.
- This branch does not require the matched instance to have a case. A snoozed instance, which has no case, can match. In that case the current instance gets `filter_action = deduplicate` with `case_id = None`. I found no guard for this. I have not tested it.

The `filter_signal` docstring says the default window is one hour. The code uses 45 minutes.

### Window defaults and units

| Where | Unit | Value as the code applies it |
|---|---|---|
| Default dedup, no filters (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) | minutes, converted to seconds | 45 min |
| `SignalFilter.window` column (`signal/models.py:206`) | seconds | Column default 3600 (1 h), used only if no value is supplied |
| `SignalFilterBase.window` (Pydantic, `signal/models.py:282`) | seconds | 600 (10 min). Create requests use this default unless they set `window` |

Because the Pydantic default is always supplied on API create, the column default of 3600 is only reached by writes that bypass that schema. The schema allows `window` to be `None`. I did not verify what happens then. `_window_start(None)` would raise, and `process_signal_batch` would catch and roll back.

### Canary signals

- `filter_snooze` does not check `canary`. A canary instance can be snoozed and is marked `snooze`.
- `filter_dedup` returns immediately for canary instances. Canary instances are never deduplicated.
- Canary instances are excluded as dedup sources in both branches (`~SignalInstance.canary`). They are never matched as the existing instance.
- A canary that is not snoozed reaches the `if signal_instance.canary: return` check. It is stored with `filter_action = none` and `case_id = None`. It does not create a case, does not run engagements, and does not run workflows.

### Functions involved

- `signal/flows.py`: `signal_instance_create_flow`, `process_signal_batch`, `process_organization_signals`, `_should_update_signal_message`, `update_signal_message`.
- `signal/service.py`: `filter_signal`, `filter_snooze`, `filter_dedup`, `_window_start`, `get_unprocessed_signal_instance_ids`.
- `database/service.py`: `apply_filters`, `apply_filter_specific_joins`.
- `config.py`: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.