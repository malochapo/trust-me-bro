For a newly processed signal instance, Dispatch checks snooze first, then deduplication, then falls through to case creation. I read `signal/service.py`, `signal/flows.py` and `signal/models.py`. Nothing was run.

## Order of checks

`signal_instance_create_flow` in `signal/flows.py` does the following:

1. It redacts the raw payload and extracts entities, saving them on `signal_instance.entities`.
2. It calls `signal_service.filter_signal`, which first calls `filter_snooze`.
3. Only if `filter_action` is still unset does `filter_signal` call `filter_dedup`.
4. If either step set an action, `filter_signal` commits and returns `True`.
5. If neither did, it sets `filter_action = none` and returns `False`.

When `filter_signal` returns `True`, the flow logs and returns without creating a case.

- If the instance has a `case_id`, the case has a conversation, and `_should_update_signal_message` agrees, it first calls `update_signal_message`.
- That update applies to deduplicated instances, not snoozed ones, which normally have no `case_id`.

If `filter_signal` returns `False`, the flow continues:

1. **Canary:** if `signal_instance.canary` is true, it returns the stored instance.
2. **Case creation off:** if `signal.create_case` is false, it returns the stored instance.
3. **New case:** otherwise it resolves case type, priority, oncall service and conversation target, calls `case_service.create`, sets `signal_instance.case`, and runs `case_flows.case_new_create_flow`. It then runs `engage_signal_identity` if the signal has engagements and entities were found, and runs any signal workflows.

The type, priority, oncall service and conversation target each take the instance's value first. They fall back to the signal's value, then to the case type's value (case type only for oncall service and conversation target; the signal supplies the priority and type).

## `filter_snooze`

It loops over `signal_instance.signal.filters` in order. A filter is considered only if `mode == active` and `action == snooze`.

- **No expiration:** the filter is skipped with a warning (`continue`).
- **Expired:** if `expiration` (treated as UTC) is at or before now, the code does `break`, not `continue`. The loop stops, so any later filters in the list are not checked.
- **Expression present:**
  - The code builds a query over `SignalInstance` rows with the same `signal_id`.
  - It applies `apply_filter_specific_joins` and `apply_filters` with the filter's JSON expression. That expression is a list of field/op/value specs on `SignalInstance` and related models such as entities.
  - It then restricts the query to `SignalInstance.id == signal_instance.id`.
  - If that returns a row, the instance is snoozed and the loop ends.
- **No expression:** the instance is snoozed unconditionally.

Snooze has no lookback window. The only time element is the filter's own `expiration` datetime.

## `filter_dedup`

**Canary:** it returns immediately if the instance is a canary (see below).

**Default dedup, when `signal.filters` is empty:**
- The window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, via `_window_start`. The config default in `config.py` is 45 minutes, overridable by env var.
- It looks for the most recent instance (`created_at` descending) of the same signal that meets all of these:
  - created within the window, measured back from now;
  - a different id from the current instance;
  - `case_id` not null;
  - not a canary.
- Entities are not compared. If one is found, the instance takes its `case_id` and gets `filter_action = deduplicate`.
- The `filter_signal` docstring says "1-hour window". The code uses 45 minutes by default.

**Filter-based dedup, when the signal has any filters:**
- It loops over filters with `mode == active` and `action == deduplicate`. Snooze filters are skipped.
- The candidate query is built from these parts:
  - same `signal_id` and not canary;
  - joins to `entities` and `entity_type`, with the filter's expression applied via `apply_filters`;
  - `created_at >= now - f.window`, where `SignalFilter.window` is in seconds and defaults to 3600 (1 hour) at the model level;
  - a second join on entities, restricted to the current instance's entity ids, so a candidate must share at least one entity with it;
  - excluding the current instance's own id.
- The results are ordered by `created_at` ascending, and the earliest match is used. The instance takes that match's `case_id` and `filter_action = deduplicate`, and the loop stops.
- There is no `case_id IS NOT NULL` condition on this path. The earliest match could have `case_id = None` (for example if it was snoozed), and the new instance would then be marked deduplicated with no case.
- Dedup filter expiration is not checked here, only in `filter_snooze`.

If a signal has filters but none are active dedup filters (for example only a snooze filter), the default dedup does not apply. The instance falls through to case creation.

## Canary signals

- **Snooze:** `filter_snooze` does not look at `canary`, so a canary can still be snoozed by a matching filter.
- **Dedup:** `filter_dedup` returns early for canaries, so they are never deduplicated into a case. Both dedup queries also exclude canary rows (`~SignalInstance.canary`), so a canary can never be the case source for others.
- **Case creation:** a canary that is not snoozed gets `filter_action = none`, and the flow then returns at the `signal_instance.canary` check. It is stored but never gets a case, workflows or engagement.