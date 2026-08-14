"""Root-cause guard for the longitudinal (السجل التراكمي) tab.

Every sibling student-analytics route in ai_routes_mod is mounted under
``/hakim`` (the router itself has no prefix, so each decorator carries the
segment explicitly). The longitudinal route was missing that segment, so the
frontend call ``GET /api/hakim/student/{id}/longitudinal`` hit no route and
returned a route-not-matched 404, leaving the cumulative-record tab empty even
when data existed.
"""

from src.modules.ai.controllers.ai_routes_mod import router


def _paths():
    return {getattr(r, "path", None) for r in router.routes}


def test_longitudinal_route_is_registered_under_hakim():
    assert "/hakim/student/{student_id}/longitudinal" in _paths()


def test_longitudinal_route_not_registered_without_hakim_prefix():
    # The bare path can never receive the frontend request and only invites
    # accidental duplicate/unscoped surfaces.
    assert "/student/{student_id}/longitudinal" not in _paths()
