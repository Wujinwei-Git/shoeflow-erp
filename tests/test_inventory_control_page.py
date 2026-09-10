from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_inventory_control_page() -> None:
    response = client.get("/inventory-control")

    assert response.status_code == 200
    assert "库存校正与库存流水" in response.text
    assert "/static/js/inventory_control.js" in response.text