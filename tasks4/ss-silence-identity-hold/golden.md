The Slack snooze submission creates an MFA challenge and then blocks in DispatchMfaPlugin.wait_for_challenge, which polls the challenge every second for timeout=300 seconds; when time runs out it sets the challenge status to EXPIRED, commits, and returns MfaChallengeStatus.EXPIRED, so no snooze filter is created.

FILE: src/dispatch/plugins/dispatch_core/plugin.py
FUNCTION: DispatchMfaPlugin.wait_for_challenge
TIMEOUT: 300 seconds
END_STATUS: expired
