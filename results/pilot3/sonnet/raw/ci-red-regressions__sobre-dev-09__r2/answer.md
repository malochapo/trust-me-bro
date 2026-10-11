The suite is green again: 351 passed and 4 skipped, with `tests/ai/test_ai_service.py` excluded as you said. I made three fixes:

1. **`src/dispatch/database/service.py`, `restricted_case_filter`**: the `IndividualContact.email == current_user.email` check was no longer tied to `Visibility.restricted`. As a result, members saw every restricted case, not just the ones they participate in. It is now `and_(restricted, email match)`, like the incident filter. This fixed `test_restricted_case_filter_with_test_data`.
2. **`src/dispatch/entity/service.py`, `find_entities`**: the "stop at the first JSONPath match" change (`[:1]`) dropped every match after the first. Paths like `asset[*].id` therefore returned one entity instead of all of them. I reverted it, which fixed `test_find_entities_with_field_only`.
3. **`src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds`**: this one no test caught. A recent commit changed `min(timestamps)` to `max(timestamps)`, but the code's own comment says the cut-off is the earliest relevant timestamp. I restored `min`, and the 19 tests in `tests/case_cost` still pass.

I haven't committed anything.