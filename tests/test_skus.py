from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TEST_BARCODE = "6971234567890"

TEST_SKU = {
    "barcode": TEST_BARCODE,
    "brand": "Nike",
    "article_number": "DD1391-100",
    "size": "EUR 42",
}


def test_first_scan_create_and_second_scan_match() -> None:
    """测试首次扫码、人工建档和再次命中。"""

    first_scan = client.get(
        f"/api/v1/skus/barcode/{TEST_BARCODE}"
    )

    assert first_scan.status_code == 404
    assert (
        first_scan.json()["code"]
        == "SKU_BARCODE_NOT_FOUND"
    )
    assert first_scan.json()["details"] == {
        "barcode": TEST_BARCODE,
        "requires_manual_entry": True,
    }

    create_response = client.post(
        "/api/v1/skus",
        json=TEST_SKU,
    )

    assert create_response.status_code == 201

    created_sku = create_response.json()["data"]

    assert created_sku["local_sku"].startswith("SKU-")
    assert created_sku["brand"] == "NIKE"
    assert created_sku["article_number"] == "DD1391-100"
    assert created_sku["size"] == "EUR 42"
    assert "sale_price" not in created_sku

    second_scan = client.get(
        f"/api/v1/skus/barcode/{TEST_BARCODE}"
    )

    assert second_scan.status_code == 200
    assert (
        second_scan.json()["data"]["local_sku"]
        == created_sku["local_sku"]
    )

    local_sku_response = client.get(
        f"/api/v1/skus/{created_sku['local_sku']}"
    )

    assert local_sku_response.status_code == 200


def test_duplicate_barcode_is_rejected() -> None:
    """测试重复条码不能创建。"""

    first_response = client.post(
        "/api/v1/skus",
        json=TEST_SKU,
    )

    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/skus",
        json={
            **TEST_SKU,
            "size": "EUR 43",
        },
    )

    assert duplicate_response.status_code == 409
    assert (
        duplicate_response.json()["code"]
        == "SKU_ALREADY_EXISTS"
    )


def test_duplicate_business_key_is_rejected() -> None:
    """测试品牌、货号、尺码组合不能重复。"""

    first_response = client.post(
        "/api/v1/skus",
        json=TEST_SKU,
    )

    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/skus",
        json={
            **TEST_SKU,
            "barcode": "6971234567891",
        },
    )

    assert duplicate_response.status_code == 409
    assert (
        duplicate_response.json()["code"]
        == "SKU_ALREADY_EXISTS"
    )


def test_multiple_skus_can_have_empty_barcode() -> None:
    """测试多个 SKU 的条码都可以为空。"""

    first_response = client.post(
        "/api/v1/skus",
        json={
            **TEST_SKU,
            "barcode": None,
        },
    )

    second_response = client.post(
        "/api/v1/skus",
        json={
            **TEST_SKU,
            "barcode": "",
            "size": "EUR 43",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    assert first_response.json()["data"]["barcode"] is None
    assert second_response.json()["data"]["barcode"] is None


def test_update_sku_status() -> None:
    """测试修改 SKU 状态。"""

    create_response = client.post(
        "/api/v1/skus",
        json=TEST_SKU,
    )

    local_sku = (
        create_response
        .json()["data"]["local_sku"]
    )

    update_response = client.put(
        f"/api/v1/skus/{local_sku}/status",
        json={
            "status": "inactive",
        },
    )

    assert update_response.status_code == 200
    assert (
        update_response.json()["data"]["status"]
        == "inactive"
    )