"""Hidden tests: the incident API's custom event routes declare their permission check."""

from fastapi.routing import APIRoute


def _permission_classes(route):
    """Every permission class of the PermissionsDependency objects in the route's dependency tree."""
    from dispatch.auth.permissions import PermissionsDependency

    found = set()

    def walk(dependant):
        for sub in dependant.dependencies:
            if isinstance(sub.call, PermissionsDependency):
                found.update(sub.call.permissions_classes)
            walk(sub)

    walk(route.dependant)
    return found


def _route(method, path_suffix):
    from dispatch.incident.views import router

    return next(
        r
        for r in router.routes
        if isinstance(r, APIRoute) and method in r.methods and r.path.endswith(path_suffix)
    )


def test_deleting_a_custom_event_requires_the_event_permission():
    from dispatch.auth.permissions import IncidentEventPermission

    route = _route("DELETE", "/{incident_id}/event/{event_uuid}")
    assert IncidentEventPermission in _permission_classes(route)


def test_creating_and_updating_custom_events_keep_their_check():
    from dispatch.auth.permissions import IncidentEventPermission

    for method in ("POST", "PATCH"):
        route = _route(method, "/{incident_id}/event")
        assert IncidentEventPermission in _permission_classes(route)
