Snooze is checked first, then deduplication, then case creation. Canary signals skip deduplication and never get a case. Everything below comes from reading the code; I did not run it.

## Entry point and order of checks

`signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`) runs these steps for each new instance:

1. Redacts `raw`, then extracts entities with `entity_service.find_entities` and saves them. Entity extraction happens before any filter check.
2. Calls `signal_service.filter_signal` (`service.py:866`), which does:
   - `filter_snooze` (`service.py:743`). This sets `filter_action = snooze` on a match.
   - `filter_dedup` (`service.py:789`), but only if `filter_action` is still unset. This sets `filter_action = deduplicate` and copies a `case_id` onto the instance on a match.
   - If neither matched, `filter_action` becomes `none`. If either matched, `filter_signal` returns `True`. It commits, and the flow returns early.
3. On a filtered instance, the flow updates the existing case's signal message if the case has a conversation and `_should_update_signal_message` agrees (`flows.py:89–100`). Workflows and engagements do not run.
4. If not filtered and `signal_instance.canary` is set, the flow returns without creating a case (`flows.py:103`).
5. If `signal.create_case` is false, it returns without a case (`flows.py:106`).
6. Otherwise it creates a case through `case_service.create`, starts the case flow, runs engagements if the signal has them and entities were found, and runs the signal's workflows.

## Snooze: `filter_snooze`

- Iterates `signal_instance.signal.filters` in list order. Skips any filter that is not `mode == active` and `action == snooze`.
- A snooze filter with no `expiration` is skipped with a warning.
- If `expiration <= now` (UTC; the stored value is treated as UTC), the loop does `break`. Any later snooze filters are not evaluated.
- The match is a query over all instances of the same `signal_id`, with `apply_filter_specific_joins` and `apply_filters` applied to `f.expression`. The instance matches if its own `id` is in the result.
- An empty expression snoozes every instance of that signal until expiration.
- There is no lookback window. The only time value is `expiration`.

## Deduplication: `filter_dedup`

Canary instances return immediately (`service.py:801`). Two paths:

**A. Signal has no filters at all** (`not signal.filters`). The default window applies:
- Lookback is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`config.py:95`, env-overridable, default **45 minutes**), converted to seconds by `_window_start`.
- Matches any other instance of the same signal with `created_at` in the window, a non-null `case_id`, and `canary` false. Entities are not compared.
- Takes the most recent match by `created_at` and copies its `case_id`.

**B. Signal has at least one filter.** Only the default path is skipped. The 45-minute default is not used, so a signal with only snooze filters gets no deduplication at all.
- Iterates filters. Skips non-`active` filters and filters whose action is not `deduplicate`.
- For each dedup filter, the query covers the same signal, non-canary instances, joined to entities and entity types. It applies `apply_filters(f.expression)`, requires `created_at >= now - f.window` seconds, and requires at least one entity ID in common with this instance. It excludes this instance and orders by `created_at` ascending.
- The first match's `case_id` is used, and the loop stops. Unlike path A, this path does not require `case_id` to be non-null. If the earliest match has no case, the instance is marked `deduplicate` with `case_id = None` and is dropped without a case.
- If the instance has no entities, `Entity.id.in_([])` matches nothing, so no deduplication happens.

## Time windows

| Mechanism | Unit | Value as the code applies it |
|---|---|---|
| Snooze | absolute datetime | `SignalFilter.expiration`, no lookback |
| Default dedup (no filters) | minutes, converted to seconds | 45 (env `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) |
| Custom dedup filter | seconds | `SignalFilter.window` |

The custom window default is inconsistent across layers:
- SQLAlchemy model `SignalFilter.window` (`signal/models.py:206`): default `60*60` = 3600 seconds.
- Pydantic `SignalFilterBase.window` (`signal/models.py:282`): default `600` = 10 minutes. `create_signal_filter` (`service.py:200`) passes this value through, so filters created through the API get 600 unless the caller sets a value.
- UI (`SignalFilterCreateDialog.vue`): labels the field "Window (minutes)" with options 5, 10, 15, 20, 30. It sends the number unchanged and I found no `* 60` conversion, so a selected 10 would be stored as 10 seconds.

The `filter_signal` docstring says the default is a 1-hour window, which does not match the 45-minute code.

## Canary signals

- **Snooze:** `filter_snooze` does not check `canary`, so a canary can be snoozed. A snoozed canary is marked and stored, with no case.
- **Dedup:** `filter_dedup` returns early for canary instances. Canary instances are also excluded from dedup candidate queries on both paths (`~SignalInstance.canary`), so they never serve as a match for other instances.
- **Case creation:** an unfiltered canary is stored with `filter_action = none` and returns at `flows.py:103`. No case, no workflows, no engagements.