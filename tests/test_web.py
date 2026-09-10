from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_erp_home_page_is_available() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "ShoeFlow ERP" in response.text
    assert "经营首页" in response.text
    assert "库存查询" in response.text


def test_erp_css_is_available() -> None:
    response = client.get(
        "/static/css/app.css"
    )

    assert response.status_code == 200
    assert "--navy-950" in response.text


def test_erp_javascript_is_available() -> None:
    response = client.get(
        "/static/js/app.js"
    )

    assert response.status_code == 200
    assert "loadDashboard" in response.text