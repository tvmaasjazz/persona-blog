from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts

from apps.api.app_factory import create_app
from libs.permissions.types import PermissionType

READ_ONLY_METHODS = {"GET", "HEAD"}
OPEN_WRITE_ROUTES = {
    ("POST", "/auth/logout"),
    ("POST", "/dev/llm/complete"),
}


def _walk_dependants(dependant: Dependant) -> Iterator[Dependant]:
    for sub_dependant in dependant.dependencies:
        yield sub_dependant
        yield from _walk_dependants(sub_dependant)


def _find_api_route_contexts(fastapi_app: FastAPI) -> list[RouteContext]:
    return [
        route_context
        for route_context in iter_route_contexts(fastapi_app.routes)
        if isinstance(route_context.original_route, APIRoute)
    ]


def _find_required_permissions(route_context: RouteContext) -> frozenset[PermissionType]:
    required_permissions: set[PermissionType] = set()
    for sub_dependant in _walk_dependants(route_context.dependant):
        required_permissions |= getattr(sub_dependant.call, "required_permissions", frozenset())
    return frozenset(required_permissions)


def test_create_app_every_write_route_requires_a_permission_or_is_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "DEVELOPMENT")
    fastapi_app = create_app()

    unguarded_write_routes = set()
    for route_context in _find_api_route_contexts(fastapi_app):
        for method in route_context.methods - READ_ONLY_METHODS:
            is_open_route = (method, route_context.path) in OPEN_WRITE_ROUTES
            if not is_open_route and not _find_required_permissions(route_context):
                unguarded_write_routes.add((method, route_context.path))

    assert unguarded_write_routes == set()


@pytest.mark.parametrize(
    ("method", "path", "expected_permission"),
    [
        pytest.param("POST", "/personas", PermissionType.PERSONA_WRITE, id="create_persona"),
        pytest.param(
            "PUT", "/personas/{persona_identity}", PermissionType.PERSONA_WRITE, id="update_persona"
        ),
        pytest.param(
            "DELETE",
            "/personas/{persona_identity}",
            PermissionType.PERSONA_WRITE,
            id="delete_persona",
        ),
        pytest.param("POST", "/blog-posts", PermissionType.BLOG_POST_WRITE, id="create_blog_post"),
        pytest.param(
            "POST",
            "/blog-posts/from-generate-text-run",
            PermissionType.BLOG_POST_WRITE,
            id="create_blog_post_from_generate_text_run",
        ),
        pytest.param(
            "PUT",
            "/blog-posts/{blog_post_identity}",
            PermissionType.BLOG_POST_WRITE,
            id="update_blog_post",
        ),
        pytest.param(
            "DELETE",
            "/blog-posts/{blog_post_identity}",
            PermissionType.BLOG_POST_WRITE,
            id="delete_blog_post",
        ),
        pytest.param(
            "POST",
            "/generate-text/blog-post",
            PermissionType.GENERATE_TEXT_RUN_WRITE,
            id="generate_blog_post",
        ),
        pytest.param(
            "POST",
            "/generate-text/runs/{run_identity}/resume",
            PermissionType.GENERATE_TEXT_RUN_WRITE,
            id="resume_generate_text",
        ),
    ],
)
def test_create_app_write_route_requires_exactly_its_permission(
    method: str, path: str, expected_permission: PermissionType
) -> None:
    fastapi_app = create_app()

    matching_routes = [
        route_context
        for route_context in _find_api_route_contexts(fastapi_app)
        if route_context.path == path and method in route_context.methods
    ]

    assert len(matching_routes) == 1
    assert _find_required_permissions(matching_routes[0]) == frozenset({expected_permission})
