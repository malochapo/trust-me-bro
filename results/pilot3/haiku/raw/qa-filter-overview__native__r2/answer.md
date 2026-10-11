Snooze is checked first, then deduplication, then case creation. Canary signals can be snoozed but are never deduplicated and never create a case. This is from reading the code only; I did not run it or its tests.

**Entry point.** `signal_instance_create_flow` in `src/dispatch/signal/flows.py` runs the sequence:

1. It redacts `raw`, then finds entities with `entity_service.find_entities` and saves them. Dedup depends on these entities, so this happens first.
2. It calls `signal_service.filter_signal`. If that returns True, the instance is filtered. The flow may update the case's signal message, then returns without creating a case.
3. If the instance is canary, it returns here without a case.
4. If `signal.create_case` is false, it returns here.
5. Otherwise it creates a case with `case_service.create`.

**Order inside `filter_signal`** (`src/dispatch/signal/service.py`):

1. `filter_snooze`. If it sets `filter_action`, dedup is skipped.
2. `filter_dedup`, only if no filter action was set yet.
3. If still no action, `filter_action` is set to `none`. Otherwise the instance counts as filtered.

**Snooze (`filter_snooze`).** It loops over `signal.filters` and considers only filters with `mode == active` and `action == snooze`.
- A snooze filter with no `expiration` is skipped with a warning.
- A filter whose `expiration` is in the past triggers `break`, which ends the whole loop. Later snooze filters are not checked.
- If the filter has an expression, the query runs `apply_filter_specific_joins` and `apply_filters` against the signal's instances, and then requires this instance's id to match. If it matches, the instance is snoozed.
- If the filter has no expression, every instance of the signal is snoozed.
- Snooze has no time window. The only time value is the absolute `expiration` datetime.

**Deduplication (`filter_dedup`).**

- Canary: returns immediately with no change.
- No filters on the signal: the default path applies. It looks for the most recent instance of the same signal, created within `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, with a non-null `case_id`, a different id, and `canary` false. Ordering is by `created_at` descending, and the first match's `case_id` is used. The default is 45 minutes (`src/dispatch/config.py`), so this is 2700 seconds. It matches on nothing else, so entities are ignored.
- Signal has any filters: the default path is skipped entirely. The code loops over filters with `mode == active` and `action == deduplicate`. It is not limited to snooze filters, so a signal with only snooze filters also never gets the default dedup.
  - The query covers the same signal and excludes canary instances. It joins entities and `entity_type`, applies `f.expression`, and requires `created_at >= now - f.window` seconds.
  - It also requires the candidate to share at least one entity with the new instance (`Entity.id.in_` over the new instance's entities). With no entities, nothing matches.
  - It excludes the instance itself and orders by `created_at` ascending. The first match's `case_id` is used, then the loop breaks.
  - This path does not require the candidate to have a case. If the earliest match has `case_id` of None, the instance is marked deduplicated with no case, and the flow treats it as filtered and creates no case.

**Time windows and defaults.**
- Snooze: `expiration`, an absolute datetime, no unit.
- Filter dedup window: `SignalFilter.window`, in seconds. The Pydantic `SignalFilterBase.window` defaults to 600 (10 minutes), which is what API-created filters get when they omit it. The SQLAlchemy column default is 3600 (1 hour). The comment on the column and the 1-hour text in the `filter_signal` docstring are not consistent with the 600 API default.
- Default dedup window: 45 minutes, configurable with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. The `filter_signal` docstring still says 1 hour.

**Canary.**
- `filter_snooze` has no canary check, so a canary instance can be snoozed. If it is, it is filtered and the flow returns.
- `filter_dedup` skips canary instances, and the candidate queries exclude canary instances. Canary instances are never deduplicated and never serve as a dedup target.
- A canary that is not snoozed is stored and returned before the `create_case` check. It never creates a case.

**Unverified.** I did not check `apply_filters` with an empty expression on a deduplicate filter, or how monitor-mode filters are recorded. Neither is in the path I traced.