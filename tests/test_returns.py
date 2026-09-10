from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_sku_inbound_and_sale(
    barcode: str,
    *,
    inbound_quantity: int = 10,
    unit_cost: str = "500.00",
    sale_quantity: int = 4,
    unit_price: str = "900.00",
) -> tuple[dict[str, object], dict[str, object]]:
    """创建 SKU、入库并销售。"""

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
            "quantity": inbound_quantity,
            "unit_cost": unit_cost,
        },
    )

    assert inbound_response.status_code == 201

    sale_response = client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": sale_quantity,
                    "unit_price": unit_price,
                }
            ]
        },
    )

    assert sale_response.status_code == 201

    sale = sale_response.json()["data"]

    return sku, sale


def test_partial_return_restores_inventory() -> None:
    """部分退货应恢复库存并更新销售状态。"""

    sku, sale = create_sku_inbound_and_sale(
        barcode="6920000000001",
    )

    response = client.post(
        "/api/v1/returns",
        json={
            "sale_no": sale["sale_no"],
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 2,
                }
            ],
            "note": "部分退货测试",
        },
    )

    assert response.status_code == 201

    returned = response.json()["data"]

    assert (
        returned["return_type"]
        == "customer_return"
    )
    assert returned["total_amount"] == "1800.00"
    assert returned["total_cost"] == "1000.00"
    assert (
        returned["gross_profit_reversal"]
        == "800.00"
    )

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    inventory = inventory_response.json()["data"]

    assert inventory["on_hand_qty"] == 8
    assert inventory["avg_cost"] == "500.00"

    sale_response = client.get(
        f"/api/v1/sales/{sale['sale_no']}"
    )

    assert (
        sale_response.json()["data"]["status"]
        == "partially_returned"
    )


def test_full_return_marks_sale_returned() -> None:
    """全部退货后销售状态应变为 returned。"""

    sku, sale = create_sku_inbound_and_sale(
        barcode="6920000000002",
        sale_quantity=4,
    )

    response = client.post(
        "/api/v1/returns",
        json={
            "sale_no": sale["sale_no"],
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 4,
                }
            ],
        },
    )

    assert response.status_code == 201

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    assert (
        inventory_response
        .json()["data"]["on_hand_qty"]
        == 10
    )

    sale_response = client.get(
        f"/api/v1/sales/{sale['sale_no']}"
    )

    assert (
        sale_response.json()["data"]["status"]
        == "returned"
    )


def test_return_quantity_cannot_exceed_remaining() -> None:
    """退货数量不能超过可退数量。"""

    sku, sale = create_sku_inbound_and_sale(
        barcode="6920000000003",
        sale_quantity=4,
    )

    response = client.post(
        "/api/v1/returns",
        json={
            "sale_no": sale["sale_no"],
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 5,
                }
            ],
        },
    )

    assert response.status_code == 409
    assert (
        response.json()["code"]
        == "RETURN_QUANTITY_EXCEEDED"
    )

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    assert (
        inventory_response
        .json()["data"]["on_hand_qty"]
        == 6
    )


def test_return_uses_original_sale_cost() -> None:
    """退货应按原销售成本回库并重新计算平均成本。"""

    sku, sale = create_sku_inbound_and_sale(
        barcode="6920000000004",
        inbound_quantity=10,
        unit_cost="500.00",
        sale_quantity=2,
    )

    second_inbound = client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": sku["local_sku"],
            "quantity": 2,
            "unit_cost": "800.00",
        },
    )

    assert second_inbound.status_code == 201

    before_return = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    ).json()["data"]

    assert before_return["on_hand_qty"] == 10
    assert before_return["avg_cost"] == "560.00"

    return_response = client.post(
        "/api/v1/returns",
        json={
            "sale_no": sale["sale_no"],
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 2,
                }
            ],
        },
    )

    assert return_response.status_code == 201

    after_return = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    ).json()["data"]

    assert after_return["on_hand_qty"] == 12
    assert after_return["avg_cost"] == "550.00"


def test_sale_reversal_restores_all_inventory() -> None:
    """整单冲销应恢复全部销售库存。"""

    sku, sale = create_sku_inbound_and_sale(
        barcode="6920000000005",
        sale_quantity=3,
    )

    response = client.post(
        f"/api/v1/sales/{sale['sale_no']}/reverse",
        json={
            "note": "销售录入错误",
        },
    )

    assert response.status_code == 201

    reversal = response.json()["data"]

    assert (
        reversal["return_type"]
        == "sale_reversal"
    )

    inventory_response = client.get(
        f"/api/v1/inventory/{sku['local_sku']}"
    )

    assert (
        inventory_response
        .json()["data"]["on_hand_qty"]
        == 10
    )

    sale_response = client.get(
        f"/api/v1/sales/{sale['sale_no']}"
    )

    assert (
        sale_response.json()["data"]["status"]
        == "reversed"
    )


def test_sale_cannot_be_reversed_twice() -> None:
    """同一销售单不能重复冲销。"""

    _, sale = create_sku_inbound_and_sale(
        barcode="6920000000006",
    )

    first_response = client.post(
        f"/api/v1/sales/{sale['sale_no']}/reverse",
        json={},
    )

    assert first_response.status_code == 201

    second_response = client.post(
        f"/api/v1/sales/{sale['sale_no']}/reverse",
        json={},
    )

    assert second_response.status_code == 409
    assert (
        second_response.json()["code"]
        == "SALE_NOT_REVERSIBLE"
    )


def test_partially_returned_sale_cannot_be_reversed() -> None:
    """已经部分退货的销售不能再整单冲销。"""

    sku, sale = create_sku_inbound_and_sale(
        barcode="6920000000007",
    )

    return_response = client.post(
        "/api/v1/returns",
        json={
            "sale_no": sale["sale_no"],
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 1,
                }
            ],
        },
    )

    assert return_response.status_code == 201

    reverse_response = client.post(
        f"/api/v1/sales/{sale['sale_no']}/reverse",
        json={},
    )

    assert reverse_response.status_code == 409
    assert (
        reverse_response.json()["code"]
        == "SALE_NOT_REVERSIBLE"
    )


def test_return_creates_positive_stock_movement() -> None:
    """退货应产生正数库存流水。"""

    sku, sale = create_sku_inbound_and_sale(
        barcode="6920000000008",
    )

    return_response = client.post(
        "/api/v1/returns",
        json={
            "sale_no": sale["sale_no"],
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 1,
                }
            ],
        },
    )

    return_no = (
        return_response
        .json()["data"]["return_no"]
    )

    movement_response = client.get(
        f"/api/v1/inventory/"
        f"{sku['local_sku']}/movements"
    )

    movements = movement_response.json()["data"]

    assert movements[0]["movement_type"] == "return"
    assert movements[0]["quantity_change"] == 1
    assert movements[0]["reference_no"] == return_no