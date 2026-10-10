Recap of the review. Five data-changing routes had no PermissionsDependency when we started. Creating cases and incidents is open on purpose, and the two case resource routes never had a check. The incident custom event delete route lost its IncidentEventPermission check in a refactor; it is restored, with a test. Members could see every restricted case because the restricted case filter was flattened into a single or_; the participant condition is back under the restricted branch.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: {plant:q5-unprotected-event-delete}
VISIBILITY_BUG: {plant:q1-restricted-case-filter}
