"""Hidden tests: a masked payload value never becomes an entity, and every other match does."""

import uuid

MASK = "[REDACTED]"


def _entity_types(project, *paths):
    from dispatch.entity_type.models import EntityType

    return [
        EntityType(name=f"mt {path}", jpath=path, regular_expression=None, project=project)
        for path in paths
    ]


def _masked_instance(payload):
    from dispatch.signal.redaction import redact_raw
    from tests.factories import SignalInstanceFactory

    raw = redact_raw({"id": str(uuid.uuid4()), **payload})
    return SignalInstanceFactory(raw=raw), raw


def test_a_masked_token_is_not_an_entity(session, project):
    from dispatch.entity.service import find_entities

    instance, raw = _masked_instance(
        {"actor": {"login": "octocat", "session_token": "ghs_16C7e42F292c6912E7710c838347Ae178B4a"}}
    )
    assert raw["actor"]["session_token"] == MASK

    assert find_entities(session, instance, _entity_types(project, "actor.session_token")) == []
    found = find_entities(session, instance, _entity_types(project, "actor.login"))
    assert [entity.value for entity in found] == ["octocat"]


def test_every_unmasked_match_is_still_an_entity(session, project):
    from dispatch.entity.service import find_entities

    instance, _ = _masked_instance(
        {
            "users": [
                {"email": "alice@example.com", "password": "correct horse"},
                {"email": "bob@example.com", "password": "battery staple"},
            ]
        }
    )

    found = find_entities(
        session, instance, _entity_types(project, "users[*].email", "users[*].password")
    )
    assert {entity.value for entity in found} == {"alice@example.com", "bob@example.com"}
