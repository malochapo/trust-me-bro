find_schedule_and_send asks the oncall plugin whether the previous person just went off shift, computes hours_in_shift from shift_start and shift_end, or 7 * 24 hours when shift_start is missing, then counts incident_service.get_all_last_x_hours incidents whose commander is that person and case_service.get_all_last_x_hours cases with their own channel (has_channel) assigned to them. Neither query filters by project, so incidents of every project in the organization count.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes
