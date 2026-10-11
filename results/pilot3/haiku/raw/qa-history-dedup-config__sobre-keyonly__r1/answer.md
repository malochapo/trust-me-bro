The commit is `7a9fe810` by Jordan Lee, "feat(signal): make the default deduplication window configurable", dated 2025-06-19. It replaced a hard-coded `timedelta(hours=1)` in the default dedup lookback with `timedelta(minutes=SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES)`, where the new setting defaults to 45 minutes. The setting is read from the environment variable `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`.

Note that the current default is 45 minutes, not 1 hour, so the window changed in value as well as becoming configurable.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (hard-coded)