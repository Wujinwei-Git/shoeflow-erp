from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_sku_and_inbound(
    barcode: str,
    size: str = "EUR 42",
    quantity: int = 10,
    unit_cost: str = "500.00",
) -> dict[str, object]:
    """创建 SKU 并完成入库。"""

    sku_response = client.post(
        "/api/v1/skus",
        json={
            "barcode": barcode,
            "brand": "Nike",
            "article_number": "DD1391-100",
            "size": size,
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


def test_create_sale_deducts_inventory() -> None:
    """销售后应扣减库存并计算利润。"""

    sku = create_sku_and_inbound(
        barcode="6910000000001",
        quantity=10,
        unit_cost="500.00",
    )

    sale_response = client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 2,
                    "unit_price": "900.00",
                }
            ],
            "note": "销售测试",
        },
    )

    assert sale_response.status_code == 201

    sale = sale_response.json()["data"]

    assert sale["status"] == "completed"
    assert sale["total_amount"] == "1800.00"
    assert sale["total_cost"] == "1000.00"
    assert sale["gross_profit"] == "800.00"

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    inventory = inventory_response.json()["data"]

    assert inventory["on_hand_qty"] == 8
    assert inventory["available_qty"] == 8
    assert inventory["avg_cost"] == "500.00"
    assert inventory["inventory_value"] == "4000.00"


def test_sale_does_not_change_average_cost() -> None:
    """销售只能减少库存，不能改变平均成本。"""

    sku = create_sku_and_inbound(
        barcode="6910000000002",
        quantity=15,
        unit_cost="600.00",
    )

    sale_response = client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 5,
                    "unit_price": "900.00",
                }
            ]
        },
    )

    assert sale_response.status_code == 201

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    inventory = inventory_response.json()["data"]

    assert inventory["on_hand_qty"] == 10
    assert inventory["avg_cost"] == "600.00"


def test_insufficient_stock_rolls_back_sale() -> None:
    """库存不足时，销售单和库存扣减都应回滚。"""

    sku = create_sku_and_inbound(
        barcode="6910000000003",
        quantity=3,
        unit_cost="500.00",
    )

    sale_response = client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 5,
                    "unit_price": "900.00",
                }
            ]
        },
    )

    assert sale_response.status_code == 409
    assert (
        sale_response.json()["code"]
        == "INSUFFICIENT_STOCK"
    )

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    assert (
        inventory_response
        .json()["data"]["on_hand_qty"]
        == 3
    )

    sales_response = client.get(
        "/api/v1/sales"
    )

    assert sales_response.status_code == 200
    assert sales_response.json()["data"] == []


def test_sale_creates_stock_movement() -> None:
    """销售应生成负数库存流水。"""

    sku = create_sku_and_inbound(
        barcode="6910000000004",
    )

    sale_response = client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 2,
                    "unit_price": "900.00",
                }
            ]
        },
    )

    assert sale_response.status_code == 201

    sale_no = (
        sale_response
        .json()["data"]["sale_no"]
    )

    movement_response = client.get(
        f"/api/v1/inventory/"
        f"{sku['local_sku']}/movements"
    )

    movements = movement_response.json()["data"]

    assert len(movements) == 2
    assert movements[0]["movement_type"] == "sale"
    assert movements[0]["quantity_change"] == -2
    assert movements[0]["reference_no"] == sale_no
    assert movements[0]["before_avg_cost"] == "500.00"
    assert movements[0]["after_avg_cost"] == "500.00"


def test_inactive_sku_cannot_be_sold() -> None:
    """暂停使用的 SKU 不允许销售。"""

    sku = create_sku_and_inbound(
        barcode="6910000000005",
    )

    status_response = client.put(
        f"/api/v1/skus/{sku['local_sku']}/status",
        json={
            "status": "inactive",
        },
    )

    assert status_response.status_code == 200

    sale_response = client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 1,
                    "unit_price": "900.00",
                }
            ]
        },
    )

    assert sale_response.status_code == 409
    assert (
        sale_response.json()["code"]
        == "SKU_NOT_ACTIVE"
    )


def test_sale_detail_can_be_queried() -> None:
    """创建后的销售单应能按单号查询。"""

    sku = create_sku_and_inbound(
        barcode="6910000000006",
    )

    create_response = client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 1,
                    "unit_price": "999.00",
                }
            ]
        },
    )

    sale_no = (
        create_response
        .json()["data"]["sale_no"]
    )

    query_response = client.get(
        f"/api/v1/sales/{sale_no}"
    )

    assert query_response.status_code == 200
    assert (
        query_response.json()["data"]["sale_no"]
        == sale_no
    )
    assert (
        query_response.json()["data"]
        ["items"][0]["unit_price"]
        == "999.00"
    )


def test_duplicate_sku_in_sale_is_rejected() -> None:
    """同一销售单不能重复出现相同 SKU。"""

    sku = create_sku_and_inbound(
        barcode="6910000000007",
    )

    response = client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 1,
                    "unit_price": "900.00",
                },
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 1,
                    "unit_price": "800.00",
                },
            ]
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["code"]
        == "VALIDATION_ERROR"
    )