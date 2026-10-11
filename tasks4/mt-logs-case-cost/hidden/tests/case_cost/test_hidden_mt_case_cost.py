"""Hidden tests: the classic response cost of src/dispatch/case_cost.

A case's classic cost stops at the earliest of the times it was escalated, marked stable or
closed. A project with no annual employee cost or no business year hours uses the project
model's default for the missing value (50000 a year, 2080 hours a year). The scheduled job
runs unwrapped (no scheduler, no per-organization session) against the test session.
"""

import inspect
import logging
from datetime import datetime, timedelta

HOUR = timedelta(hours=1)


def _job(name):
    import dispatch.case_cost.scheduled  # noqa: F401  (registers the job)
    from dispatch.scheduler import scheduler

    task = next(t for t in scheduler.registered_tasks if t["name"] == name)
    return inspect.unwrap(task["func"])


def _setup(session, case, participant, participant_role, assumed_at, annual=52000, hours=2080):
    """One assignee (full engagement) since `assumed_at`; 52000 / 2080 is 25 an hour."""
    from dispatch.participant_role.models import ParticipantRoleType

    participant_role.role = ParticipantRoleType.assignee
    participant_role.assumed_at = assumed_at
    participant_role.renounced_at = None
    participant.participant_roles = [participant_role]
    case.participants = [participant]
    case.case_type.cost_model = None
    case.project.annual_employee_cost = annual
    case.project.business_year_hours = hours
    session.add(case)
    session.commit()


def _classic_cost(session, case):
    from dispatch.case.enums import CostModelType
    from dispatch.case_cost.service import get_or_create_case_response_cost_by_model_type

    return get_or_create_case_response_cost_by_model_type(
        case=case, model_type=CostModelType.classic, db_session=session
    )


def test_escalated_then_stable_case_cost_stops_at_escalation(
    case, session, participant, participant_role
):
    from dispatch.case.enums import CaseStatus
    from dispatch.case_cost.service import calculate_case_response_cost_classic

    now = datetime.utcnow().replace(microsecond=0)
    _setup(session, case, participant, participant_role, assumed_at=now - 10 * HOUR)
    case.status = CaseStatus.stable
    case.escalated_at = now - 8 * HOUR
    case.stable_at = now - HOUR
    case.closed_at = None
    session.commit()

    # two hours in the role before the escalation, at 25 an hour
    assert calculate_case_response_cost_classic(case=case, db_session=session) == 50


def test_stable_then_closed_case_cost_stops_when_stable(
    case, session, participant, participant_role
):
    from dispatch.case.enums import CaseStatus
    from dispatch.case_cost.service import calculate_case_response_cost_classic

    now = datetime.utcnow().replace(microsecond=0)
    _setup(session, case, participant, participant_role, assumed_at=now - 10 * HOUR)
    case.status = CaseStatus.closed
    case.escalated_at = None
    case.stable_at = now - 8 * HOUR
    case.closed_at = now - HOUR
    session.commit()

    assert calculate_case_response_cost_classic(case=case, db_session=session) == 50


def test_hourly_job_keeps_escalation_cut_off_when_case_turns_stable(
    case, session, participant, participant_role
):
    from dispatch.case.enums import CaseStatus

    now = datetime.utcnow().replace(microsecond=0)
    _setup(session, case, participant, participant_role, assumed_at=now - 10 * HOUR)
    case.status = CaseStatus.stable
    case.escalated_at = now - 8 * HOUR
    case.stable_at = now - HOUR
    case.closed_at = None
    session.commit()
    # the cost as the job last computed it, an hour before the escalation (written with a
    # plain UPDATE, which the updated_at hook of the ORM does not see)
    cost = _classic_cost(session, case)
    table = cost.__table__
    session.execute(
        table.update().where(table.c.id == cost.id).values(amount=25, updated_at=now - 9 * HOUR)
    )
    session.commit()
    session.expire_all()

    _job("calculate-cases-response-cost")(db_session=session, project=case.project)

    session.expire_all()
    assert _classic_cost(session, case).amount == 50


def test_hourly_job_costs_case_of_project_without_annual_employee_cost(
    case, session, participant, participant_role, caplog
):
    from dispatch.case.enums import CaseStatus

    now = datetime.utcnow().replace(microsecond=0)
    # just under two hours in the role, at the default 50000 / 2080 (25 an hour)
    _setup(
        session,
        case,
        participant,
        participant_role,
        assumed_at=now - 2 * HOUR + timedelta(seconds=30),
        annual=None,
    )
    case.status = CaseStatus.triage
    case.escalated_at = case.stable_at = case.closed_at = None
    session.commit()

    with caplog.at_level(logging.ERROR):
        _job("calculate-cases-response-cost")(db_session=session, project=case.project)
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR], "the job logged an error"

    session.expire_all()
    assert _classic_cost(session, case).amount == 50


def test_project_without_business_year_hours_uses_the_default(
    case, session, participant, participant_role
):
    from dispatch.case.enums import CaseStatus
    from dispatch.case_cost.service import calculate_case_response_cost_classic

    now = datetime.utcnow().replace(microsecond=0)
    # 52000 a year over the default 2080 hours is 25 an hour
    _setup(session, case, participant, participant_role, assumed_at=now - 3 * HOUR, hours=None)
    case.status = CaseStatus.stable
    case.escalated_at = case.closed_at = None
    case.stable_at = now - HOUR
    session.commit()

    assert calculate_case_response_cost_classic(case=case, db_session=session) == 50
