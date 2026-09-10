from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_business_data() -> dict[str, object]:
    """创建统计测试所需业务数据。"""

    sku_response = client.post(
        "/api/v1/skus",
        json={
            "barcode": "6940000000001",
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
            "quantity": 10,
            "unit_cost": "500.00",
        },
    )

    assert inbound_response.status_code == 201

    sale_response = client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "local_sku": sku["local_sku"],
                    "quantity": 4,
                    "unit_price": "900.00",
                }
            ]
        },
    )

    assert sale_response.status_code == 201

    sale = sale_response.json()["data"]

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

    return {
        "sku": sku,
        "sale": sale,
    }


def test_overview_calculates_net_business_data() -> None:
    """总览应正确计算库存、销售、退货和净利润。"""

    create_business_data()

    response = client.get(
        "/api/v1/analytics/overview"
    )

    assert response.status_code == 200

    data = response.json()["data"]

    inventory = data["inventory"]
    sales = data["sales"]

    assert inventory["sku_count"] == 1
    assert inventory["on_hand_qty"] == 7
    assert inventory["available_qty"] == 7
    assert inventory["inventory_value"] == "3500.00"

    assert sales["gross_units_sold"] == 4
    assert sales["returned_units"] == 1
    assert sales["net_units_sold"] == 3

    assert sales["gross_sales_amount"] == "3600.00"
    assert sales["return_amount"] == "900.00"
    assert sales["net_sales_amount"] == "2700.00"

    assert sales["gross_sales_cost"] == "2000.00"
    assert sales["return_cost"] == "500.00"
    assert sales["net_sales_cost"] == "1500.00"

    assert sales["net_gross_profit"] == "1200.00"


def test_inventory_analytics_returns_sku_stock() -> None:
    """库存统计应返回SKU库存和库存金额。"""

    business_data = create_business_data()
    sku = business_data["sku"]

    response = client.get(
        "/api/v1/analytics/inventory"
    )

    assert response.status_code == 200

    items = response.json()["data"]

    assert len(items) == 1
    assert items[0]["local_sku"] == sku["local_sku"]
    assert items[0]["on_hand_qty"] == 7
    assert items[0]["avg_cost"] == "500.00"
    assert items[0]["inventory_value"] == "3500.00"


def test_low_stock_endpoint() -> None:
    """低库存接口应根据阈值筛选SKU。"""

    create_business_data()

    low_response = client.get(
        "/api/v1/analytics/low-stock",
        params={
            "threshold": 7,
        },
    )

    assert low_response.status_code == 200
    assert len(low_response.json()["data"]) == 1

    not_low_response = client.get(
        "/api/v1/analytics/low-stock",
        params={
            "threshold": 6,
        },
    )

    assert not_low_response.status_code == 200
    assert not_low_response.json()["data"] == []


def test_sales_by_sku_calculates_net_sales() -> None:
    """SKU销售统计应扣除退货。"""

    business_data = create_business_data()
    sku = business_data["sku"]

    response = client.get(
        "/api/v1/analytics/sales-by-sku"
    )

    assert response.status_code == 200

    items = response.json()["data"]

    assert len(items) == 1

    item = items[0]

    assert item["local_sku"] == sku["local_sku"]
    assert item["gross_units_sold"] == 4
    assert item["returned_or_reversed_units"] == 1
    assert item["net_units_sold"] == 3
    assert item["net_sales_amount"] == "2700.00"
    assert item["net_sales_cost"] == "1500.00"
    assert item["net_gross_profit"] == "1200.00"


def test_reversed_sale_has_zero_net_result() -> None:
    """销售冲销后净销售额、成本和利润应归零。"""

    sku_response = client.post(
        "/api/v1/skus",
        json={
            "barcode": "6940000000002",
            "brand": "Nike",
            "article_number": "DD1391-100",
            "size": "EUR 42",
            "sale_price": "900.00",
            "status": "active",
        },
    )

    sku = sku_response.json()["data"]

    client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": sku["local_sku"],
            "quantity": 5,
            "unit_cost": "500.00",
        },
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

    sale_no = (
        sale_response
        .json()["data"]["sale_no"]
    )

    reverse_response = client.post(
        f"/api/v1/sales/{sale_no}/reverse",
        json={
            "note": "统计冲销测试",
        },
    )

    assert reverse_response.status_code == 201

    response = client.get(
        "/api/v1/analytics/overview"
    )

    sales = response.json()["data"]["sales"]

    assert sales["gross_sales_amount"] == "1800.00"
    assert sales["reversal_amount"] == "1800.00"
    assert sales["net_sales_amount"] == "0.00"
    assert sales["net_sales_cost"] == "0.00"
    assert sales["net_gross_profit"] == "0.00"
    assert sales["net_units_sold"] == 0


def test_daily_sales_returns_business_date() -> None:
    """每日销售统计应返回日期和净经营结果。"""

    create_business_data()

    response = client.get(
        "/api/v1/analytics/daily-sales"
    )

    assert response.status_code == 200

    items = response.json()["data"]

    assert len(items) >= 1

    total_net_sales = sum(
        float(item["net_sales_amount"])
        for item in items
    )

    assert total_net_sales == 2700.0


def test_invalid_date_range_is_rejected() -> None:
    """开始日期不能晚于结束日期。"""

    response = client.get(
        "/api/v1/analytics/overview",
        params={
            "date_from": "2026-09-10",
            "date_to": "2026-09-01",
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["code"]
        == "INVALID_DATE_RANGE"
    )