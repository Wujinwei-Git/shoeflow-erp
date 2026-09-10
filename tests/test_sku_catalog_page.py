from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_sku_catalog_page() -> None:
    response = client.get("/sku-catalog")

    assert response.status_code == 200
    assert "SKU 商品档案" in response.text
    assert "/static/js/sku_catalog.js" in response.text