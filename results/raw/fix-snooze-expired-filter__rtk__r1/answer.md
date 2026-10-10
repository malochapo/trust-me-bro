I fixed the bug and added a regression test, but I couldn't run the test. The environment is missing the project's dependencies, and `pip install -e .` fails while building `dkimpy` and `sentry-asgi`. Without them `tests/conftest.py` doesn't import (first `easydict`, then `slack_sdk`).

**Cause:** in `filter_snooze` (`src/dispatch/signal/service.py`), an expired snooze filter hit `break` instead of `continue`. The loop stopped at the expired filter, so a valid filter later in the list was never checked. With a single filter this didn't show. Once the second filter was added, the expired one was reached first and snoozing stopped working for that user.

**Fix:** the expired-filter check now uses `continue`, so the loop moves on to the next filter.

**Regression test:** `test_filter_actions_snooze_expired_and_valid` in `tests/signal/test_signal_service.py`. It gives a signal an expired snooze filter (7 days ago) listed before a valid one (30 days out), both matching the same entity. It asserts the instance ends up snoozed.

If you run `python -m pytest tests/signal/test_signal_service.py -k snooze` in an environment with the dependencies installed, that would confirm both the new test and the existing snooze tests.

I also ran `pip install easydict` in the environment while trying to get the tests running.