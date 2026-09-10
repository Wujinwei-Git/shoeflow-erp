from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_sales_page() -> None:
    response = client.get("/sales")

    assert response.status_code == 200
    assert "销售出库" in response.text
    assert "/static/js/sales.js" in response.text