## How a new signal instance is routed

The decision runs in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`). That function redacts the raw payload, extracts entities, and then calls `signal_service.filter_signal` (`service.py`). `filter_signal` runs snooze first, and dedup only if snooze did not match. A new case is created only if neither matched.

**Order of checks**

1. `filter_snooze(...)` runs over `signal.filters`. If it sets `filter_action = snooze`, the instance is filtered.
2. Only if `filter_action` is still empty, `filter_dedup(...)` runs. If it sets `filter_action = deduplicate` and `case_id`, the instance is filtered.
3. If nothing matched, `filter_signal` sets `filter_action = none` and returns `False`.
4. If the instance was filtered, the flow returns early. It updates the existing case's Slack signal message if that case has a conversation. No case is created.
5. Otherwise the flow handles canaries, then `create_case`, then case creation, `case_new_create_flow`, engagements, and workflows.

**Snooze: `filter_snooze`**

- It only considers filters with `mode == active` and `action == snooze`.
- A snooze filter with no `expiration` is skipped with a warning.
- If `expiration <= now` (UTC), the loop hits `break`. That exits the whole loop, so later snooze filters are not evaluated either.
- If `expression` is empty, every instance of the signal is snoozed until expiration.
- If `expression` is set, the filter is applied to all instances of the same `signal_id`, and the instance is snoozed only if it matches. This check has no time window; it asks whether this instance matches the expression.
- `expiration` is an absolute `DateTime`, not a duration.

**Deduplication: `filter_dedup`**

There are two paths, selected by whether the signal has any filters at all.

*No filters on the signal (default path):*
- Window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. `config.py:95` defaults this to **45 minutes**, so 2700 seconds.
- It matches the most recent (`created_at desc`) instance of the same signal that has a non-null `case_id`, is not canary, and is not this instance. Entities are not compared.

*Signal has filters:*
- It loops over filters with `mode == active` and `action == deduplicate`. Only the first matching filter is applied.
- The query covers the same signal, non-canary instances, and `apply_filters(query, f.expression)`. Entities are joined, and the instance must share at least one entity with the new instance.
- The window is `f.window` seconds, with a `created_at >= now - window` cutoff. The model column default is 3600 (1 hour). The Pydantic `SignalFilterBase.window` default is **600 seconds (10 minutes)**, which is what applies when a filter is created through the API without `window`.
- It orders by `created_at asc` and takes the earliest match, using its `case_id`.
- If a deduplicate filter's `expression` is empty, no filter criteria beyond the signal, entity, and window constraints are applied.

If there are filters but none is an active deduplicate filter that matches, no dedup happens.

**Canary signals**

- `filter_dedup` returns immediately for a canary instance. Canaries are never deduplicated.
- Canary instances are excluded from being dedup targets in both paths.
- `filter_snooze` does not skip canaries, so a canary can still be snoozed.
- If not snoozed, a canary gets `filter_action = none`. In the flow, the canary branch (`flows.py`, after the filter check) stores it and returns. No case is created and no workflows run.

## Things I noticed while reading

- **Stale docstring:** `filter_signal`'s docstring says the default dedup window is 1 hour. The code uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **Dedup target without a case:** the filter-driven dedup path does not require `case_id IS NOT NULL`, unlike the default path. Snoozed instances and canaries have no case, and snoozed instances are not excluded from this query. If the earliest match is a snoozed instance, the new instance gets `filter_action = deduplicate` with `case_id = None`, so no case is created for it. I read this from the code and did not run it.
- **Filter order:** `Signal.filters` is a plain relationship with no explicit ordering, so the code does not guarantee which filter is checked first.

I did not run the test suite or a reproduction; these conclusions come from reading `service.py`, `flows.py`, `models.py`, and `config.py`.