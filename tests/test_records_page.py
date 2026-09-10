from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_records_page() -> None:
    response = client.get("/records")

    assert response.status_code == 200
    assert "销售与退货记录" in response.text
    assert "/static/js/records.js" in response.text