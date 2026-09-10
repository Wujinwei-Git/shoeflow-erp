from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_returns_page() -> None:
    response = client.get("/returns")

    assert response.status_code == 200
    assert "退货与销售冲销" in response.text
    assert "/static/js/returns.js" in response.text