const refreshButton = document.getElementById("refreshButton");
const searchInput = document.getElementById("searchInput");

const salesPanel = document.getElementById("salesPanel");
const returnsPanel = document.getElementById("returnsPanel");
const salesBody = document.getElementById("salesBody");
const returnsBody = document.getElementById("returnsBody");
const salesEmpty = document.getElementById("salesEmpty");
const returnsEmpty = document.getElementById("returnsEmpty");
const messageBox = document.getElementById("messageBox");

const detailModal = document.getElementById("detailModal");
const closeModalButton = document.getElementById("closeModalButton");

let salesRecords = [];
let returnRecords = [];
let activeTab = "sales";


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function money(value) {
    return `¥${Number(value || 0).toFixed(2)}`;
}


function formatDate(value) {
    if (!value) {
        return "-";
    }

    return String(value).replace("T", " ").slice(0, 19);
}

function getRecordDate(record) {
    return (
        record.sold_at ??
        record.returned_at ??
        record.created_at ??
        record.updated_at ??
        null
    );
}


function normalizeList(data) {
    if (Array.isArray(data)) {
        return data;
    }

    if (Array.isArray(data?.items)) {
        return data.items;
    }

    if (Array.isArray(data?.records)) {
        return data.records;
    }

    return [];
}


function showMessage(message, type = "error") {
    messageBox.textContent = message;
    messageBox.className = `message-box ${type}`;
}


function hideMessage() {
    messageBox.textContent = "";
    messageBox.className = "message-box hidden";
}


async function readJson(response) {
    const result = await response.json().catch(() => null);

    if (!result) {
        throw new Error("服务器没有返回有效数据");
    }

    return result;
}


function statusText(status) {
    const values = {
        completed: "已完成",
        partially_returned: "部分退货",
        returned: "全部退货",
        reversed: "已冲销"
    };

    return values[status] || status || "-";
}


function statusClass(status) {
    const allowed = [
        "completed",
        "partially-returned",
        "returned",
        "reversed"
    ];

    const normalized = String(status || "")
        .replaceAll("_", "-");

    return allowed.includes(normalized)
        ? normalized
        : "completed";
}


function getQuantity(record) {
    if (record.total_quantity != null) {
        return Number(record.total_quantity);
    }

    if (record.quantity != null) {
        return Number(record.quantity);
    }

    if (Array.isArray(record.items)) {
        return record.items.reduce(
            (total, item) => total + Number(item.quantity || 0),
            0
        );
    }

    return 0;
}


function getAmount(record) {
    return Number(
        record.total_amount ??
        record.refund_amount ??
        record.gross_amount ??
        0
    );
}


function renderSales() {
    const keyword = searchInput.value.trim().toLowerCase();

    const records = salesRecords.filter(record =>
        String(record.sale_no || "")
            .toLowerCase()
            .includes(keyword)
    );

    salesBody.innerHTML = "";
    salesEmpty.classList.toggle("hidden", records.length > 0);

    records.forEach(record => {
        const row = document.createElement("tr");

        function getFormatDate() {
            return formatDate(getRecordDate(record));
        }

        row.innerHTML = `
            <td class="order-number">
                ${escapeHtml(record.sale_no)}
            </td>

            <td>${(getFormatDate())}</td>
            <td>${getQuantity(record)} 双</td>
            <td>${money(getAmount(record))}</td>

            <td>
                <span class="status-badge
                    status-${statusClass(record.status)}">
                    ${escapeHtml(statusText(record.status))}
                </span>
            </td>

            <td>
                <button
                    class="table-button sale-detail-button"
                    data-sale-no="${escapeHtml(record.sale_no)}"
                    type="button"
                >
                    查看明细
                </button>

                <a
                    class="table-link"
                    href="/returns?sale_no=${encodeURIComponent(record.sale_no)}"
                >
                    退货/冲销
                </a>
            </td>
        `;

        salesBody.appendChild(row);
    });

    document.querySelectorAll(".sale-detail-button").forEach(button => {
        button.addEventListener("click", () => {
            openSaleDetail(button.dataset.saleNo);
        });
    });
}


function renderReturns() {
    const keyword = searchInput.value.trim().toLowerCase();

    const records = returnRecords.filter(record => {
        const returnNumber = String(record.return_no || "").toLowerCase();
        const saleNumber = String(record.sale_no || "").toLowerCase();

        return (
            returnNumber.includes(keyword) ||
            saleNumber.includes(keyword)
        );
    });

    returnsBody.innerHTML = "";
    returnsEmpty.classList.toggle("hidden", records.length > 0);

    records.forEach(record => {
        const row = document.createElement("tr");

        row.innerHTML = `
            <td class="order-number">
                ${escapeHtml(record.return_no)}
            </td>

            <td>${escapeHtml(record.sale_no || "-")}</td>
            <td>${formatDate(getRecordDate(record))}</td>
            <td>${getQuantity(record)} 双</td>
            <td>${money(getAmount(record))}</td>

            <td>
                <button
                    class="table-button return-detail-button"
                    data-return-no="${escapeHtml(record.return_no)}"
                    type="button"
                >
                    查看明细
                </button>
            </td>
        `;

        returnsBody.appendChild(row);
    });

    document.querySelectorAll(".return-detail-button").forEach(button => {
        button.addEventListener("click", () => {
            openReturnDetail(button.dataset.returnNo);
        });
    });
}


function renderActivePanel() {
    if (activeTab === "sales") {
        renderSales();
    } else {
        renderReturns();
    }
}

async function loadDetail(path, fallback) {
    try {
        const response = await fetch(path);
        const result = await readJson(response);

        if (response.ok && result.data) {
            return result.data;
        }
    } catch (error) {
        console.warn("详情加载失败：", path);
    }

    return fallback;
}
async function loadRecords() {
    hideMessage();
    refreshButton.disabled = true;
    refreshButton.textContent = "正在刷新……";

    try {
        const [salesResponse, returnsResponse] = await Promise.all([
            fetch("/api/v1/sales"),
            fetch("/api/v1/returns")
        ]);

        const [salesResult, returnsResult] = await Promise.all([
            readJson(salesResponse),
            readJson(returnsResponse)
        ]);

        if (!salesResponse.ok) {
            throw new Error(salesResult.message || "销售记录查询失败");
        }

        if (!returnsResponse.ok) {
            throw new Error(returnsResult.message || "退货记录查询失败");
        }

        const salesList = normalizeList(salesResult.data);
        const returnsList = normalizeList(returnsResult.data);

        salesRecords = await Promise.all(
            salesList.map(record =>
                loadDetail(
                    `/api/v1/sales/${encodeURIComponent(record.sale_no)}`,
                    record
                )
            )
        );

        returnRecords = await Promise.all(
            returnsList.map(record =>
                loadDetail(
                    `/api/v1/returns/${encodeURIComponent(record.return_no)}`,
                    record
                )
            )
        );

        document.getElementById("salesCount").textContent =
            salesRecords.length;

        document.getElementById("returnsCount").textContent =
            returnRecords.length;

        renderSales();
        renderReturns();
    } catch (error) {
        showMessage(error.message || "业务记录查询失败");
    } finally {
        refreshButton.disabled = false;
        refreshButton.textContent = "刷新记录";
    }
}


function renderDetailItems(items) {
    const body = document.getElementById("detailItemsBody");
    body.innerHTML = "";

    const records = Array.isArray(items) ? items : [];

    records.forEach(item => {
        const quantity = Number(item.quantity || 0);
        const unitPrice = Number(
            item.unit_price ??
            item.refund_unit_price ??
            0
        );

        const row = document.createElement("tr");

        row.innerHTML = `
            <td>
                <strong>
                    ${escapeHtml(item.brand || "")}
                    ${escapeHtml(item.article_number || item.local_sku || "")}
                </strong>
                <br>
                <small>
                    ${escapeHtml(item.size || "")}
                    ${escapeHtml(item.local_sku || "")}
                </small>
            </td>

            <td>${quantity} 双</td>
            <td>${money(unitPrice)}</td>

            <td>
                ${money(
                    item.line_amount ??
                    item.refund_amount ??
                    quantity * unitPrice
                )}
            </td>
        `;

        body.appendChild(row);
    });
}


function showDetailModal() {
    detailModal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
}


function closeDetailModal() {
    detailModal.classList.add("hidden");
    document.body.style.overflow = "";
}


async function openSaleDetail(saleNumber) {
    try {
        const response = await fetch(
            `/api/v1/sales/${encodeURIComponent(saleNumber)}`
        );

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "销售明细查询失败");
        }

        const sale = result.data;

        document.getElementById("detailType").textContent = "销售单";
        document.getElementById("detailNumber").textContent =
            sale.sale_no || "-";

        document.getElementById("detailSummary").innerHTML = `
            <div>
                <span>销售时间</span>
                <strong>${formatDate(getRecordDate(sale))}</strong>
            </div>

            <div>
                <span>销售数量</span>
                <strong>${getQuantity(sale)} 双</strong>
            </div>

            <div>
                <span>销售金额</span>
                <strong>${money(getAmount(sale))}</strong>
            </div>
        `;

        renderDetailItems(sale.items);

        document.getElementById("detailActions").innerHTML = `
            <a
                class="detail-action-link"
                href="/returns?sale_no=${encodeURIComponent(sale.sale_no)}"
            >
                办理退货或冲销
            </a>
        `;

        showDetailModal();
    } catch (error) {
        showMessage(error.message || "销售明细查询失败");
    }
}


async function openReturnDetail(returnNumber) {
    try {
        const response = await fetch(
            `/api/v1/returns/${encodeURIComponent(returnNumber)}`
        );

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "退货明细查询失败");
        }

        const record = result.data;

        document.getElementById("detailType").textContent = "退货单";
        document.getElementById("detailNumber").textContent =
            record.return_no || "-";

        document.getElementById("detailSummary").innerHTML = `
            <div>
                <span>原销售单</span>
                <strong>${escapeHtml(record.sale_no || "-")}</strong>
            </div>

            <div>
                <span>退货数量</span>
                <strong>${getQuantity(record)} 双</strong>
            </div>

            <div>
                <span>退款金额</span>
                <strong>${money(getAmount(record))}</strong>
            </div>
        `;

        renderDetailItems(record.items);
        document.getElementById("detailActions").innerHTML = "";

        showDetailModal();
    } catch (error) {
        showMessage(error.message || "退货明细查询失败");
    }
}


document.querySelectorAll(".record-tab").forEach(button => {
    button.addEventListener("click", () => {
        activeTab = button.dataset.tab;

        document.querySelectorAll(".record-tab").forEach(tab => {
            tab.classList.toggle("active", tab === button);
        });

        salesPanel.classList.toggle(
            "hidden",
            activeTab !== "sales"
        );

        returnsPanel.classList.toggle(
            "hidden",
            activeTab !== "returns"
        );

        searchInput.placeholder = activeTab === "sales"
            ? "输入销售单号搜索"
            : "输入退货单号或原销售单号搜索";

        searchInput.value = "";
        renderActivePanel();
    });
});

searchInput.addEventListener("input", renderActivePanel);
refreshButton.addEventListener("click", loadRecords);
closeModalButton.addEventListener("click", closeDetailModal);

document.querySelectorAll("[data-close-modal]").forEach(element => {
    element.addEventListener("click", closeDetailModal);
});

document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        closeDetailModal();
    }
});

window.addEventListener("DOMContentLoaded", loadRecords);