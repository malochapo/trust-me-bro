## How a new signal instance is routed

The entry point is `signal_instance_create_flow` in `src/dispatch/signal/flows.py:46`. After redaction and entity extraction, it calls `signal_service.filter_signal` (`src/dispatch/signal/service.py:866`). Only if that call reports "not filtered" does the flow go on to case creation.

**Order of checks in `filter_signal`:**

1. **`filter_snooze`** (`service.py:743`) runs first. If it sets a `filter_action`, deduplication is skipped.
2. **`filter_dedup`** (`service.py:789`) runs only if nothing was snoozed.
3. If neither set a `filter_action`, it is set to `SignalFilterAction.none` and the instance is not filtered. Otherwise `filtered = True`. The session is committed and the result returned.

**Back in the flow:**

- If filtered, the flow returns. It updates the Slack signal message if the linked case has a conversation. No case is created.
- If `signal_instance.canary`, it returns without creating a case.
- If `signal.create_case` is false, it returns.
- Otherwise it resolves case type, priority, oncall, and conversation target, then creates the case (the rest of the flow, not traced here).

## Snooze (`filter_snooze`)

Iterates `signal.filters` in order. For each filter:

- Skipped unless `mode == active` and `action == snooze`.
- No `expiration`: logs a warning and continues.
- `expiration <= now` (UTC; a naive datetime is treated as UTC): **`break`**. This ends the whole loop, so later snooze filters are not checked.
- Empty `expression`: snoozes every instance of the signal, regardless of entity.
- Non-empty `expression`: runs `apply_filter_specific_joins` and `apply_filters` against the signal's instances and snoozes only if the new instance's `id` is in the result. Matching is on the expression, typically entity fields.

There is no snooze window. The only time value is `expiration`, an absolute datetime. Snooze has no canary check, so a canary can be snoozed.

Snooze filters created through Slack (`_create_snooze_filter`, `src/dispatch/plugins/dispatch_slack/case/interactive.py:970`) set `expiration = now + delta`, where `delta` comes from the relative date picker. Selected entities become the expression. With no entities selected, the expression is `[]`.

## Deduplication (`filter_dedup`)

**Canary:** returns immediately. Canary instances are also excluded from every candidate query (`~SignalInstance.canary`).

**Branch A: the signal has no filters at all** (`not signal_instance.signal.filters`):

- Window: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` from `src/dispatch/config.py:95`, an env-configurable value in **minutes**, default **45**. Converted with `* 60` to seconds.
- Matches the most recent (`created_at desc`) instance of the same signal in that window that has a non-null `case_id`, excluding itself. No entity matching.
- On match: copies that `case_id` and sets `deduplicate`.

**Branch B: the signal has one or more filters.** The default window is not applied at all, even if none of the filters match. For each filter:

- Skipped unless `mode == active` and `action == deduplicate`.
- Candidates: same signal, non-canary, joined to entities and entity types, matching `f.expression`, with `created_at >= now - f.window`, sharing at least one entity with the new instance, excluding itself. Ordered by `created_at asc`, first match wins.
- Window: `SignalFilter.window`, in **seconds**. The DB column default is 3600 (1 hour). The API schema `SignalFilterBase.window` defaults to 600 (10 minutes), so filters created through the schema get 600 unless a value is supplied.

## Things the code does that may surprise you

- **Branch B does not require the matched instance to have a case.** Branch A filters on `case_id IS NOT NULL`; Branch B does not. Snoozed instances have no case, so a deduplicate filter can match a snoozed instance, copy its null `case_id`, and mark the new instance `deduplicate`. The result is that it is filtered and no case is created.
- **Any existing filter disables the 45-minute default.** The check is `not signal.filters`, not "no active dedup filter", so a signal with only an inactive or snooze filter gets no default dedup.
- **Expired snooze filters stop the scan.** The `break` at `service.py:763` means a single expired snooze filter prevents later snooze filters on the same signal from being evaluated.
- **Stale docstring.** The `filter_signal` docstring says "1-hour window". The code uses 45 minutes in Branch A.

## Canary signals

- Snooze is applied to canaries (no check), so a canary can get `filter_action = snooze`.
- Deduplication is skipped for canaries, and canaries are never matched as dedup targets.
- A canary that is not snoozed gets `filter_action = none` from `filter_signal`. It returns from the flow at the `canary` check (`flows.py:102`) without creating a case, so its `case_id` stays null.

I read the code but did not run tests or execute these paths against a database. The Branch B null-case behavior is inferred from the query and has not been confirmed with a test.