Every path that adds someone to a case's conversation goes through conversation_flows.add_case_participants. For a thread case (case.has_thread) it only calls add_to_thread when case.signal_instances is not empty and case.signal_instances[0].signal.lifecycle == "production"; a case reported by hand has no signal instances, so nobody is brought into its thread. Channel cases always get the people added.

FILE: src/dispatch/conversation/flows.py
FUNCTION: add_case_participants
HAND_OPENED: no
REQUIRED_MARK: production
