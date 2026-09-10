const saleNumberInput = document.getElementById("saleNumberInput");
const searchButton = document.getElementById("searchButton");
const selectAllButton = document.getElementById("selectAllButton");
const submitReturnButton = document.getElementById("submitReturnButton");
const reverseButton = document.getElementById("reverseButton");
const continueButton = document.getElementById("continueButton");

const messageBox = document.getElementById("messageBox");
const saleCard = document.getElementById("saleCard");
const reversalCard = document.getElementById("reversalCard");
const successCard = document.getElementById("successCard");
const returnItemsBody = document.getElementById("returnItemsBody");

let currentSale = null;
let returnItems = [];


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


function showMessage(message, type = "error") {
    messageBox.textContent = message;
    messageBox.className = `message-box ${type}`;
}


function hideMessage() {
    messageBox.textContent = "";
    messageBox.className = "message-box hidden";
}


function setLoading(button, loading, text) {
    if (!button.dataset.originalText) {
        button.dataset.originalText = button.textContent;
    }

    button.disabled = loading;
    button.textContent = loading
        ? text
        : button.dataset.originalText;
}


async function readJson(response) {
    const result = await response.json().catch(() => null);

    if (!result) {
        throw new Error("服务器没有返回有效数据");
    }

    return result;
}


function getReturnedQuantity(item) {
    return Number(
        item.returned_quantity ??
        item.returned_qty ??
        0
    );
}


function getRemainingQuantity(item) {
    const soldQuantity = Number(item.quantity || 0);
    const returnedQuantity = getReturnedQuantity(item);

    return Math.max(
        0,
        Number(
            item.returnable_quantity ??
            item.remaining_quantity ??
            soldQuantity - returnedQuantity
        )
    );
}


function statusText(status) {
    const values = {
        completed: "销售已完成",
        partially_returned: "部分退货",
        returned: "已全部退货",
        reversed: "已冲销"
    };

    return values[status] || status || "-";
}


function renderSale(sale) {
    currentSale = sale;

    const saleItems = Array.isArray(sale.items)
        ? sale.items
        : [];

    returnItems = saleItems.map(item => ({
        localSku: item.local_sku,
        barcode: item.barcode || "",
        brand: item.brand || "",
        articleNumber: item.article_number || "",
        size: item.size || "",
        soldQuantity: Number(item.quantity || 0),
        returnedQuantity: getReturnedQuantity(item),
        remainingQuantity: getRemainingQuantity(item),
        returnQuantity: 0,
        unitPrice: Number(item.unit_price || 0)
    }));

    document.getElementById("saleNumberText").textContent =
        sale.sale_no || "-";

    document.getElementById("saleCreatedAt").textContent =
        sale.created_at || "-";

    document.getElementById("saleQuantity").textContent =
        `${sale.total_quantity ?? sale.quantity ?? 0} 双`;

    document.getElementById("saleAmount").textContent =
        money(sale.total_amount ?? sale.gross_amount ?? 0);

    const statusElement = document.getElementById("saleStatus");
    statusElement.textContent = statusText(sale.status);
    statusElement.className = "sale-status";

    if (sale.status === "reversed") {
        statusElement.classList.add("reversed");
    }

    renderItems();

    saleCard.classList.remove("hidden");

    const cannotReverse =
        sale.status === "reversed" ||
        returnItems.some(item => item.returnedQuantity > 0);

    reversalCard.classList.toggle("hidden", cannotReverse);

    if (returnItems.every(item => item.remainingQuantity === 0)) {
        submitReturnButton.disabled = true;
        selectAllButton.disabled = true;
        showMessage("这张销售单已经没有可退数量", "info");
    } else {
        submitReturnButton.disabled = false;
        selectAllButton.disabled = false;
    }
}


function renderItems() {
    returnItemsBody.innerHTML = "";

    returnItems.forEach(item => {
        const row = document.createElement("tr");
        const disabled = item.remainingQuantity === 0;

        row.innerHTML = `
            <td>
                <div class="return-product">
                    <strong>
                        ${escapeHtml(item.brand)}
                        ${escapeHtml(item.articleNumber)}
                    </strong>
                    <span>
                        ${escapeHtml(item.size)}
                        · ${escapeHtml(item.localSku)}
                    </span>
                </div>
            </td>

            <td>${item.soldQuantity} 双</td>
            <td>${item.returnedQuantity} 双</td>
            <td>${item.remainingQuantity} 双</td>

            <td>
                <input
                    class="return-quantity"
                    type="number"
                    min="0"
                    max="${item.remainingQuantity}"
                    step="1"
                    value="${item.returnQuantity}"
                    data-local-sku="${escapeHtml(item.localSku)}"
                    ${disabled ? "disabled" : ""}
                >
            </td>

            <td>${money(item.unitPrice)}</td>
        `;

        returnItemsBody.appendChild(row);
    });

    document.querySelectorAll(".return-quantity").forEach(input => {
        input.addEventListener("change", event => {
            const localSku = event.target.dataset.localSku;
            const item = returnItems.find(
                row => row.localSku === localSku
            );

            const quantity = Number(event.target.value);

            if (!item) {
                return;
            }

            if (
                !Number.isInteger(quantity) ||
                quantity < 0 ||
                quantity > item.remainingQuantity
            ) {
                showMessage(
                    `本次退货数量必须在 0 到 ${item.remainingQuantity} 之间`
                );

                event.target.value = item.returnQuantity;
                return;
            }

            item.returnQuantity = quantity;
            hideMessage();
        });
    });
}


async function searchSale() {
    const saleNumber = saleNumberInput.value.trim();

    hideMessage();
    saleCard.classList.add("hidden");
    reversalCard.classList.add("hidden");
    successCard.classList.add("hidden");
    currentSale = null;

    if (!saleNumber) {
        showMessage("请输入销售单号");
        saleNumberInput.focus();
        return;
    }

    setLoading(searchButton, true, "查询中……");

    try {
        const response = await fetch(
            `/api/v1/sales/${encodeURIComponent(saleNumber)}`
        );

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "销售单查询失败");
        }

        renderSale(result.data);
        showMessage("销售单查询成功，请选择退货数量", "info");
    } catch (error) {
        showMessage(error.message || "销售单查询失败");
    } finally {
        setLoading(searchButton, false, "查询中……");
    }
}


function selectAllReturnable() {
    returnItems.forEach(item => {
        item.returnQuantity = item.remainingQuantity;
    });

    hideMessage();
    renderItems();
}


async function submitReturn() {
    if (!currentSale) {
        showMessage("请先查询销售单");
        return;
    }

    const selectedItems = returnItems.filter(
        item => item.returnQuantity > 0
    );

    if (selectedItems.length === 0) {
        showMessage("请至少填写一项退货数量");
        return;
    }

    const invalidItem = selectedItems.find(item =>
        !Number.isInteger(item.returnQuantity) ||
        item.returnQuantity > item.remainingQuantity
    );

    if (invalidItem) {
        showMessage("退货数量超过了该商品的剩余可退数量");
        return;
    }

    const payload = {
        sale_no: currentSale.sale_no,
        items: selectedItems.map(item => ({
            local_sku: item.localSku,
            quantity: item.returnQuantity
        })),
        note:
            document.getElementById("returnNote").value.trim() || null
    };

    setLoading(submitReturnButton, true, "正在办理退货……");
    hideMessage();

    try {
        const response = await fetch("/api/v1/returns", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "退货失败");
        }

        const returnedQuantity = selectedItems.reduce(
            (total, item) => total + item.returnQuantity,
            0
        );

        saleCard.classList.add("hidden");
        reversalCard.classList.add("hidden");
        successCard.classList.remove("hidden");

        document.getElementById("successTitle").textContent =
            "退货成功";

        document.getElementById("successText").textContent =
            `本次共退回 ${returnedQuantity} 双，库存已经按原销售成本恢复。`;

        document.getElementById("resultNumber").textContent =
            `退货单号：${result.data.return_no || "-"}`;
    } catch (error) {
        showMessage(error.message || "退货失败");
    } finally {
        setLoading(
            submitReturnButton,
            false,
            "正在办理退货……"
        );
    }
}


async function reverseSale() {
    if (!currentSale) {
        showMessage("请先查询销售单");
        return;
    }

    const reason =
        document.getElementById("reversalReason").value.trim();

    if (!reason) {
        showMessage("请填写冲销原因");
        return;
    }

    const confirmed = window.confirm(
        `确定要冲销销售单 ${currentSale.sale_no} 吗？\n\n` +
        "冲销后，该销售单扣减的库存将全部恢复。"
    );

    if (!confirmed) {
        return;
    }

    setLoading(reverseButton, true, "正在冲销……");
    hideMessage();

    try {
        const response = await fetch(
            `/api/v1/sales/${encodeURIComponent(currentSale.sale_no)}/reverse`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    reason: reason,
                    note: reason
                })
            }
        );

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "销售冲销失败");
        }

        saleCard.classList.add("hidden");
        reversalCard.classList.add("hidden");
        successCard.classList.remove("hidden");

        document.getElementById("successTitle").textContent =
            "销售冲销成功";

        document.getElementById("successText").textContent =
            "原销售单已经冲销，相关库存已经恢复，并生成了反向库存流水。";

        document.getElementById("resultNumber").textContent =
            `销售单号：${currentSale.sale_no}`;
    } catch (error) {
        showMessage(error.message || "销售冲销失败");
    } finally {
        setLoading(reverseButton, false, "正在冲销……");
    }
}


function resetPage() {
    currentSale = null;
    returnItems = [];

    saleNumberInput.value = "";
    document.getElementById("returnNote").value = "";
    document.getElementById("reversalReason").value = "";

    saleCard.classList.add("hidden");
    reversalCard.classList.add("hidden");
    successCard.classList.add("hidden");

    hideMessage();
    saleNumberInput.focus();
}


searchButton.addEventListener("click", searchSale);
selectAllButton.addEventListener("click", selectAllReturnable);
submitReturnButton.addEventListener("click", submitReturn);
reverseButton.addEventListener("click", reverseSale);
continueButton.addEventListener("click", resetPage);

saleNumberInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
        event.preventDefault();
        searchSale();
    }
});

window.addEventListener("DOMContentLoaded", () => {
    const parameters = new URLSearchParams(window.location.search);
    const saleNumber = parameters.get("sale_no");

    if (saleNumber) {
        saleNumberInput.value = saleNumber;
        searchSale();
    } else {
        saleNumberInput.focus();
    }
});