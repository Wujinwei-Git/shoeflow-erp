from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_inbound_page() -> None:
    response = client.get("/inbound")

    assert response.status_code == 200
    assert "扫码入库" in response.text
    assert "/static/js/inbound.js" in response.text