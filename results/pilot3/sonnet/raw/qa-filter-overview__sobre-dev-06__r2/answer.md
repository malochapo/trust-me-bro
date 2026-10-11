Everything below comes from `signal/flows.py` and `signal/service.py`, plus `signal/models.py` and `config.py` for the defaults.

## Order of checks

`signal_instance_create_flow` (`signal/flows.py`) runs these steps in order:

1. It loads the instance and redacts `raw` with `redact_raw`.
2. It extracts entities with `entity_service.find_entities`. This uses the signal's entity types plus the types scoped `all`. The result is stored on `signal_instance.entities` and committed.
3. It calls `signal_service.filter_signal`, which runs `filter_snooze` first.
4. If `filter_snooze` set no action, `filter_signal` runs `filter_dedup`.
5. If neither set an action, `filter_signal` sets `filter_action = none`. It returns `True` only if snooze or dedup acted. It commits in every case.
6. If `filter_signal` returned `True`, the flow logs and returns. If the instance has a `case_id`, its case has a conversation, and `_should_update_signal_message` says so, it calls `update_signal_message`. No new case is created.
7. Otherwise, if the instance is a canary, the flow returns, so the instance is stored but no case is created.
8. Otherwise, if `signal.create_case` is false, the flow returns.
9. Otherwise the flow resolves the case type, priority, oncall and conversation target. It then creates the case with `case_service.create`, sets `signal_instance.case`, and runs `case_flows.case_new_create_flow`. It then calls `engage_signal_identity` if the signal has engagements and entities were found, and runs the signal's workflows.

## Snooze: `filter_snooze`

It loops over `signal_instance.signal.filters` and skips any filter that isn't `mode == active` with `action == snooze`.

- **No expiration:** a filter with no `expiration` logs a warning and is skipped.
- **Expired filter:** if `expiration` (treated as UTC) is at or before now, the code does `break`, not `continue`. The first expired snooze filter therefore ends the loop, and any later snooze filters are never evaluated.
- **No expression:** an empty `expression` snoozes every instance of the signal.
- **With an expression:** the code builds a `SignalInstance` query scoped to the same `signal_id`. It applies `apply_filter_specific_joins` and `apply_filters` with the expression, and requires `SignalInstance.id == this instance's id`. If the instance matches, it sets `filter_action = snooze` and breaks. The match is on whatever the expression references, such as instance fields or entities, evaluated by the database layer.

The only time value is the `expiration` timestamp. Snoozing has no window.

## Deduplication: `filter_dedup`

**Canary:** if `signal_instance.canary` is true, it returns immediately, so a canary is never deduplicated. Canary instances are also excluded from the candidate matches (`~SignalInstance.canary`).

**No filters on the signal at all:** this is the default rule.
- It looks for the most recent other instance (`created_at` descending) of the same signal.
- That instance must have `created_at >= now - SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60 seconds`, have a non-null `case_id`, and not be a canary.
- Entities are not considered.
- The default is **45 minutes**, from `config.py` (env var `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, cast to int).
- On a match it copies that `case_id` onto the instance and sets `filter_action = deduplicate`.

The `filter_signal` docstring says "1-hour window", but the code uses the 45-minute config value.

**Signal has filters:** the default rule is skipped entirely, even if none of those filters is a dedup filter. In that case nothing deduplicates. For each filter with `mode == active` and `action == deduplicate`, it builds a query that:

- scopes to the same `signal_id` and excludes canaries;
- joins `SignalInstance.entities` and then `Entity.entity_type`;
- applies the filter's `expression` with `apply_filters`;
- requires `created_at >= now - f.window`, where `SignalFilter.window` is in **seconds**. The column default is 3600 (1 hour). The pydantic model `SignalFilterBase` defaults it to 600 (10 minutes), so filters created through the API default to 600 seconds unless the caller sets it;
- joins `SignalInstance.entities` a second time and requires `Entity.id` to be in the current instance's entity ids, so a candidate must share at least one entity with the new instance;
- excludes the instance itself.

It orders the candidates by `created_at` ascending, takes the earliest, and copies its `case_id`. It sets `filter_action = deduplicate` and stops at the first filter that matches.

The query does not require the matched instance to have a `case_id`. If the earliest match has none, `case_id` is set to `None`, but `filter_action` is still `deduplicate`. The instance is then treated as filtered and no case is created.

An instance with no entities matches no entity-based dedup filter, because the entity-id list is empty. The inner joins also require candidates to have entities.

## Canary signals

- A canary is never snoozed-exempt: `filter_snooze` has no canary check, so an active snooze filter can still mark a canary as snoozed.
- A canary is never deduplicated, and it is never used as a dedup target.
- If it is not snoozed, the flow stores it and returns before case creation.