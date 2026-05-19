def test_healthz_returns_status_and_request_id(client) -> None:
    response = client.get("/healthz", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"
    assert response.json() == {
        "status": "ok",
        "service": "InferenceLab API",
        "environment": "test",
    }
