from fastapi import Query
from fastapi.testclient import TestClient

from inflab.api.app import create_app
from inflab.config import AppSettings


def test_not_found_uses_unified_error_response(client) -> None:
    response = client.get("/missing", headers={"X-Request-ID": "missing-request"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "missing-request"
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "request_id": "missing-request",
            "details": None,
        }
    }


def test_validation_errors_use_unified_error_response() -> None:
    app = create_app(settings=AppSettings(environment="test", log_level="WARNING"))

    @app.get("/items")
    async def list_items(limit: int = Query(gt=0)) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get("/items?limit=0", headers={"X-Request-ID": "validation-request"})

    payload = response.json()

    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "validation-request"
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "Request validation failed."
    assert payload["error"]["request_id"] == "validation-request"
    assert payload["error"]["details"][0]["loc"] == ["query", "limit"]


def test_unhandled_errors_use_unified_error_response() -> None:
    app = create_app(settings=AppSettings(environment="test", log_level="WARNING"))

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom", headers={"X-Request-ID": "boom-request"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "Internal server error.",
            "request_id": "boom-request",
            "details": None,
        }
    }
