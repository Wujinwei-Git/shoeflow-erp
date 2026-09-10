from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_sku_and_inbound(
    barcode: str,
    *,
    quantity: int = 6,
    unit_cost: str = "600.00",
) -> dict[str, object]:
    """创建SKU并完成入库。"""

    sku_response = client.post(
        "/api/v1/skus",
        json={
            "barcode": barcode,
            "brand": "Nike",
            "article_number": "DD1391-100",
            "size": "EUR 42",
            "status": "active",
        },
    )

    assert sku_response.status_code == 201

    sku = sku_response.json()["data"]

    inbound_response = client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": sku["local_sku"],
            "quantity": quantity,
            "unit_cost": unit_cost,
        },
    )

    assert inbound_response.status_code == 201

    return sku


def test_decrease_duplicate_scan_inventory() -> None:
    """重复扫码时可以手动减少库存。"""

    sku = create_sku_and_inbound(
        barcode="6930000000001",
        quantity=6,
    )

    response = client.post(
        "/api/v1/inventory/corrections",
        json={
            "local_sku": sku["local_sku"],
            "quantity_change": -1,
            "reason": "duplicate_scan",
            "note": "实际5双，重复扫码1双",
        },
    )

    assert response.status_code == 201

    correction = response.json()["data"]

    assert correction["before_qty"] == 6
    assert correction["after_qty"] == 5
    assert correction["quantity_change"] == -1
    assert correction["unit_cost"] == "600.00"
    assert (
        correction["inventory_value_change"]
        == "-600.00"
    )
    assert correction["before_avg_cost"] == "600.00"
    assert correction["after_avg_cost"] == "600.00"

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    inventory = inventory_response.json()["data"]

    assert inventory["on_hand_qty"] == 5
    assert inventory["avg_cost"] == "600.00"
    assert inventory["inventory_value"] == "3000.00"


def test_increase_missed_scan_with_current_cost() -> None:
    """漏扫时可以按当前平均成本增加库存。"""

    sku = create_sku_and_inbound(
        barcode="6930000000002",
        quantity=5,
    )

    response = client.post(
        "/api/v1/inventory/corrections",
        json={
            "local_sku": sku["local_sku"],
            "quantity_change": 1,
            "reason": "missed_scan",
            "note": "实际6双，漏扫1双",
        },
    )

    assert response.status_code == 201

    correction = response.json()["data"]

    assert correction["before_qty"] == 5
    assert correction["after_qty"] == 6
    assert correction["unit_cost"] == "600.00"
    assert correction["after_avg_cost"] == "600.00"


def test_increase_with_different_cost() -> None:
    """增加库存时可以填写不同成本并重新计算平均成本。"""

    sku = create_sku_and_inbound(
        barcode="6930000000003",
        quantity=5,
        unit_cost="600.00",
    )

    response = client.post(
        "/api/v1/inventory/corrections",
        json={
            "local_sku": sku["local_sku"],
            "quantity_change": 1,
            "unit_cost": "800.00",
            "reason": "missed_scan",
        },
    )

    assert response.status_code == 201

    correction = response.json()["data"]

    assert correction["before_qty"] == 5
    assert correction["after_qty"] == 6
    assert correction["after_avg_cost"] == "633.33"

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    assert (
        inventory_response
        .json()["data"]["avg_cost"]
        == "633.33"
    )


def test_correction_cannot_make_stock_negative() -> None:
    """校正后库存不能为负数。"""

    sku = create_sku_and_inbound(
        barcode="6930000000004",
        quantity=2,
    )

    response = client.post(
        "/api/v1/inventory/corrections",
        json={
            "local_sku": sku["local_sku"],
            "quantity_change": -3,
            "reason": "duplicate_scan",
        },
    )

    assert response.status_code == 409
    assert (
        response.json()["code"]
        == "CORRECTION_STOCK_TOO_LOW"
    )

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    assert (
        inventory_response
        .json()["data"]["on_hand_qty"]
        == 2
    )


def test_zero_cost_sku_requires_cost_when_increasing() -> None:
    """零库存且零成本时，增加库存必须填写成本。"""

    sku_response = client.post(
        "/api/v1/skus",
        json={
            "barcode": "6930000000005",
            "brand": "Nike",
            "article_number": "DD1391-100",
            "size": "EUR 42",
            "sale_price": "899.00",
            "status": "active",
        },
    )

    sku = sku_response.json()["data"]

    response = client.post(
        "/api/v1/inventory/corrections",
        json={
            "local_sku": sku["local_sku"],
            "quantity_change": 1,
            "reason": "missed_scan",
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["code"]
        == "CORRECTION_UNIT_COST_REQUIRED"
    )


def test_correction_creates_adjustment_movement() -> None:
    """库存校正应生成 adjustment 流水。"""

    sku = create_sku_and_inbound(
        barcode="6930000000006",
    )

    correction_response = client.post(
        "/api/v1/inventory/corrections",
        json={
            "local_sku": sku["local_sku"],
            "quantity_change": -1,
            "reason": "duplicate_scan",
        },
    )

    correction_no = (
        correction_response
        .json()["data"]["correction_no"]
    )

    movement_response = client.get(
        f"/api/v1/inventory/"
        f"{sku['local_sku']}/movements"
    )

    movements = movement_response.json()["data"]

    assert movements[0]["movement_type"] == "adjustment"
    assert movements[0]["quantity_change"] == -1
    assert movements[0]["reference_no"] == correction_no


def test_correction_detail_can_be_queried() -> None:
    """库存校正记录可以按编号查询。"""

    sku = create_sku_and_inbound(
        barcode="6930000000007",
    )

    create_response = client.post(
        "/api/v1/inventory/corrections",
        json={
            "local_sku": sku["local_sku"],
            "quantity_change": -1,
            "reason": "duplicate_scan",
        },
    )

    correction_no = (
        create_response
        .json()["data"]["correction_no"]
    )

    query_response = client.get(
        f"/api/v1/inventory/corrections/"
        f"{correction_no}"
    )

    assert query_response.status_code == 200
    assert (
        query_response.json()["data"]
        ["correction_no"]
        == correction_no
    )