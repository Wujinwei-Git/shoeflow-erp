from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": "SUCCESS",
        "message": "success",
        "data": {
            "service": "ShoeFlow ERP",
            "version": "1.0.0",
            "environment": "test",
            "status": "healthy",
        },
    }


def test_openapi_document_is_available() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "ShoeFlow ERP"

