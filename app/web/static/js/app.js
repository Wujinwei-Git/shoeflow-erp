const state = {
    currentView: "dashboard",
    inventory: [],
};

const viewConfiguration = {
    dashboard: {
        title: "经营首页",
        description: "查看当前库存和经营情况",
    },
    inventory: {
        title: "库存查询",
        description: "查询每个 SKU 的库存和成本",
    },
};


async function requestApi(url) {
    const response = await fetch(url);

    let body;

    try {
        body = await response.json();
    } catch {
        throw new Error("服务器返回了无法识别的数据");
    }

    if (!response.ok || body.code !== "SUCCESS") {
        throw new Error(
            body.message || "请求失败"
        );
    }

    return body.data;
}


function formatMoney(value) {
    const numberValue = Number(value || 0);

    return new Intl.NumberFormat(
        "zh-CN",
        {
            style: "currency",
            currency: "CNY",
            minimumFractionDigits: 2,
        }
    ).format(numberValue);
}


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function showToast(message, isError = false) {
    const toast = document.getElementById("toast");

    toast.textContent = message;
    toast.classList.toggle("error", isError);
    toast.classList.add("visible");

    window.clearTimeout(showToast.timer);

    showToast.timer = window.setTimeout(
        () => {
            toast.classList.remove("visible");
        },
        2600
    );
}


function setText(elementId, value) {
    const element = document.getElementById(
        elementId
    );

    if (element) {
        element.textContent = value;
    }
}


function setCurrentView(viewName) {
    state.currentView = viewName;

    document
        .querySelectorAll(".nav-item")
        .forEach((button) => {
            button.classList.toggle(
                "active",
                button.dataset.view === viewName
            );
        });

    document
        .querySelectorAll(".view-panel")
        .forEach((panel) => {
            panel.classList.add("hidden");
        });

    document
        .getElementById(`${viewName}-view`)
        .classList.remove("hidden");

    const configuration = (
        viewConfiguration[viewName]
    );

    setText(
        "page-title",
        configuration.title
    );

    setText(
        "page-description",
        configuration.description
    );

    if (viewName === "inventory") {
        loadInventory();
    }
}


function renderOverview(data) {
    const inventory = data.inventory;
    const sales = data.sales;

    setText(
        "on-hand-qty",
        inventory.on_hand_qty
    );

    setText(
        "inventory-value",
        formatMoney(inventory.inventory_value)
    );

    setText(
        "net-sales-amount",
        formatMoney(sales.net_sales_amount)
    );

    setText(
        "net-gross-profit",
        formatMoney(sales.net_gross_profit)
    );

    setText(
        "gross-units-sold",
        `${sales.gross_units_sold} 双`
    );

    setText(
        "returned-units",
        `${sales.returned_units} 双`
    );

    setText(
        "reversed-units",
        `${sales.reversed_units} 双`
    );

    setText(
        "net-units-sold",
        `${sales.net_units_sold} 双`
    );

    setText(
        "gross-sales-amount",
        formatMoney(sales.gross_sales_amount)
    );

    setText(
        "return-amount",
        formatMoney(sales.return_amount)
    );

    setText(
        "net-sales-cost",
        formatMoney(sales.net_sales_cost)
    );

    setText(
        "summary-profit",
        formatMoney(sales.net_gross_profit)
    );
}


function renderDailySales(items) {
    const tableBody = document.getElementById(
        "daily-sales-body"
    );

    if (!items.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-cell">
                    暂无销售数据
                </td>
            </tr>
        `;

        return;
    }

    tableBody.innerHTML = items
        .slice()
        .reverse()
        .map((item) => {
            const profit = Number(
                item.net_gross_profit
            );

            const profitClass = (
                profit < 0
                    ? "negative-money"
                    : "positive-money"
            );

            return `
                <tr>
                    <td>${escapeHtml(item.business_date)}</td>
                    <td>${formatMoney(item.gross_sales_amount)}</td>
                    <td>${formatMoney(item.deduction_amount)}</td>
                    <td>${formatMoney(item.net_sales_amount)}</td>
                    <td>${formatMoney(item.net_sales_cost)}</td>
                    <td class="${profitClass}">
                        ${formatMoney(item.net_gross_profit)}
                    </td>
                </tr>
            `;
        })
        .join("");
}


function getStatusInformation(status) {
    const statusMap = {
        active: {
            label: "正常",
            className: "status-active",
        },
        inactive: {
            label: "暂停",
            className: "status-inactive",
        },
        discontinued: {
            label: "停止经营",
            className: "status-discontinued",
        },
    };

    return (
        statusMap[status]
        || {
            label: status,
            className: "",
        }
    );
}


function renderInventory(items) {
    const tableBody = document.getElementById(
        "inventory-table-body"
    );

    if (!items.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-cell">
                    没有符合条件的库存
                </td>
            </tr>
        `;

        return;
    }

    tableBody.innerHTML = items
        .map((item) => {
            const status = getStatusInformation(
                item.status
            );

            return `
                <tr>
                    <td>${escapeHtml(item.brand)}</td>
                    <td>${escapeHtml(item.article_number)}</td>
                    <td>${escapeHtml(item.size)}</td>
                    <td>${escapeHtml(item.barcode || "-")}</td>
                    <td>
                        <span class="status-badge ${status.className}">
                            ${escapeHtml(status.label)}
                        </span>
                    </td>
                    <td>${item.on_hand_qty} 双</td>
                    <td>${formatMoney(item.avg_cost)}</td>        
                    <td>${formatMoney(item.inventory_value)}</td>
                </tr>
            `;
        })
        .join("");
}


function filterInventory() {
    const input = document.getElementById(
        "inventory-search"
    );

    const keyword = input.value
        .trim()
        .toUpperCase();

    if (!keyword) {
        renderInventory(state.inventory);
        return;
    }

    const filteredItems = state.inventory.filter(
        (item) => {
            const searchableText = [
                item.local_sku,
                item.barcode,
                item.brand,
                item.article_number,
                item.size,
            ]
                .filter(Boolean)
                .join(" ")
                .toUpperCase();

            return searchableText.includes(keyword);
        }
    );

    renderInventory(filteredItems);
}


async function loadDashboard() {
    try {
        const [overview, dailySales] = (
            await Promise.all([
                requestApi(
                    "/api/v1/analytics/overview"
                ),
                requestApi(
                    "/api/v1/analytics/daily-sales"
                ),
            ])
        );

        renderOverview(overview);
        renderDailySales(dailySales);

    } catch (error) {
        showToast(error.message, true);
    }
}


async function loadInventory() {
    try {
        state.inventory = await requestApi(
            "/api/v1/analytics/inventory"
        );

        filterInventory();

    } catch (error) {
        showToast(error.message, true);
    }
}


async function refreshCurrentView() {
    const button = document.getElementById(
        "refresh-button"
    );

    button.disabled = true;
    button.textContent = "刷新中……";

    try {
        if (state.currentView === "dashboard") {
            await loadDashboard();
        } else {
            await loadInventory();
        }

        showToast("数据已刷新");

    } finally {
        button.disabled = false;
        button.textContent = "刷新数据";
    }
}


function registerEvents() {
    document
        .querySelectorAll(".nav-item")
        .forEach((button) => {
            button.addEventListener(
                "click",
                () => {
                    setCurrentView(
                        button.dataset.view
                    );
                }
            );
        });

    document
        .getElementById("refresh-button")
        .addEventListener(
            "click",
            refreshCurrentView
        );

    document
        .getElementById("inventory-search")
        .addEventListener(
            "input",
            filterInventory
        );
}


async function initializeApplication() {
    registerEvents();
    await loadDashboard();
}


document.addEventListener(
    "DOMContentLoaded",
    initializeApplication
);