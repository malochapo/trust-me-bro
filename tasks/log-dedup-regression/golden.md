The deploy of 2025-08-14 20:05 UTC shipped a commit that reads SignalFilter.window as seconds, while the UI stores minutes, so a 120-minute window became 120 seconds.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: Per-filter deduplication windows are now computed in seconds instead of minutes, so the 120-minute window is 120 seconds.
INTRODUCED_BY: {plant:p4-dedup-window-seconds}
