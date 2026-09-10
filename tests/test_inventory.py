from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_test_sku(
    barcode: str,
    size: str = "EUR 42",
) -> dict[str, object]:
    """创建测试 SKU。"""

    response = client.post(
        "/api/v1/skus",
        json={
            "barcode": barcode,
            "brand": "Nike",
            "article_number": "DD1391-100",
            "size": size,
            "status": "active",
        },
    )

    assert response.status_code == 201

    return response.json()["data"]


def test_new_sku_has_zero_inventory() -> None:
    """新 SKU 的初始库存应为 0。"""

    sku = create_test_sku(
        barcode="6900000000001",
    )

    response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    assert response.status_code == 200

    inventory = response.json()["data"]

    assert inventory["on_hand_qty"] == 0
    assert inventory["reserved_qty"] == 0
    assert inventory["available_qty"] == 0
    assert inventory["avg_cost"] == "0.00"
    assert inventory["inventory_value"] == "0.00"


def test_first_inbound_updates_inventory() -> None:
    """第一次入库应增加库存并建立平均成本。"""

    sku = create_test_sku(
        barcode="6900000000002",
    )

    response = client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": sku["local_sku"],
            "quantity": 10,
            "unit_cost": "500.00",
            "reference_no": "PO-20260901-001",
            "note": "第一次测试入库",
        },
    )

    assert response.status_code == 201

    data = response.json()["data"]
    inventory = data["inventory"]
    movement = data["movement"]

    assert inventory["on_hand_qty"] == 10
    assert inventory["reserved_qty"] == 0
    assert inventory["available_qty"] == 10
    assert inventory["avg_cost"] == "500.00"
    assert inventory["inventory_value"] == "5000.00"

    assert movement["movement_type"] == "inbound"
    assert movement["quantity_change"] == 10
    assert movement["before_qty"] == 0
    assert movement["after_qty"] == 10
    assert movement["after_avg_cost"] == "500.00"


def test_second_inbound_calculates_moving_average_cost() -> None:
    """第二次入库应重新计算移动平均成本。"""

    sku = create_test_sku(
        barcode="6900000000003",
    )

    first_response = client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": sku["local_sku"],
            "quantity": 10,
            "unit_cost": "500.00",
        },
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": sku["local_sku"],
            "quantity": 5,
            "unit_cost": "800.00",
        },
    )

    assert second_response.status_code == 201

    inventory = (
        second_response
        .json()["data"]["inventory"]
    )

    assert inventory["on_hand_qty"] == 15
    assert inventory["available_qty"] == 15
    assert inventory["avg_cost"] == "600.00"
    assert inventory["inventory_value"] == "9000.00"

    query_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    assert query_response.status_code == 200
    assert (
        query_response.json()["data"]["avg_cost"]
        == "600.00"
    )


def test_stock_movements_can_be_queried() -> None:
    """库存流水应能被查询。"""

    sku = create_test_sku(
        barcode="6900000000004",
    )

    for quantity, unit_cost in [
        (10, "500.00"),
        (5, "800.00"),
    ]:
        response = client.post(
            "/api/v1/inventory/inbounds",
            json={
                "local_sku": sku["local_sku"],
                "quantity": quantity,
                "unit_cost": unit_cost,
            },
        )

        assert response.status_code == 201

    movement_response = client.get(
        f"/api/v1/inventory/"
        f"{sku['local_sku']}/movements"
    )

    assert movement_response.status_code == 200

    movements = movement_response.json()["data"]

    assert len(movements) == 2
    assert movements[0]["unit_cost"] == "800.00"
    assert movements[1]["unit_cost"] == "500.00"


def test_inactive_sku_cannot_be_inbound() -> None:
    """暂停使用的 SKU 不允许入库。"""

    sku = create_test_sku(
        barcode="6900000000005",
    )

    status_response = client.put(
        f"/api/v1/skus/{sku['local_sku']}/status",
        json={
            "status": "inactive",
        },
    )

    assert status_response.status_code == 200

    inbound_response = client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": sku["local_sku"],
            "quantity": 10,
            "unit_cost": "500.00",
        },
    )

    assert inbound_response.status_code == 409
    assert (
        inbound_response.json()["code"]
        == "SKU_NOT_ACTIVE"
    )


def test_invalid_inbound_quantity_is_rejected() -> None:
    """入库数量不能为 0 或负数。"""

    sku = create_test_sku(
        barcode="6900000000006",
    )

    response = client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": sku["local_sku"],
            "quantity": 0,
            "unit_cost": "500.00",
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["code"]
        == "VALIDATION_ERROR"
    )