from fastapi.testclient import TestClient

from v2.main import app


def test_protected_endpoint_uses_error_envelope():
    with TestClient(app) as client:
        response = client.get("/api/v2/tasks/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "HTTP_401"
    assert response.json()["request_id"]


def test_validation_error_uses_error_envelope():
    with TestClient(app) as client:
        response = client.post("/api/v2/auth/register", json={"phone": "1", "password": "x"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
