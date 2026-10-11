When a signal definition has no filters, the default dedup window applies, and it is 45 minutes. The docstring of `filter_signal` in `signal/service.py` still says "1-hour window", but that text is out of date. The code uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, and the default for that setting is 45.

An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to a whole number of minutes. `config.py` reads it with `config(..., cast=int, default=45)`.

I did not trace the rest of the dedup path (`filter_dedup` and what it does with a match) beyond the window calculation.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py