Recap: the per-filter deduplication window was read as seconds by the refactor that shared the lookback computation, and the snooze refactor stopped at the first expired snooze filter. Both are fixed, with regression tests. Signals without any filter are grouped over the default window, which is configurable.

DEDUP_WINDOW_BUG: {plant:p4-dedup-window-seconds}
SNOOZE_BUG: {plant:p5-snooze-refactor}
CANARY: {plant:e46fa023b7b8899f4a5f24336ce84699618ed196}
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
