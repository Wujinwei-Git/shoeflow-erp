const barcodeInput = document.getElementById("barcodeInput");
const searchButton = document.getElementById("searchButton");
const minusButton = document.getElementById("minusButton");
const plusButton = document.getElementById("plusButton");
const quantityChangeInput = document.getElementById("quantityChange");
const correctionReason = document.getElementById("correctionReason");
const submitCorrectionButton =
    document.getElementById("submitCorrectionButton");
const refreshMovementsButton =
    document.getElementById("refreshMovementsButton");

const messageBox = document.getElementById("messageBox");
const productSection = document.getElementById("productSection");
const movementsBody = document.getElementById("movementsBody");
const emptyMovements = document.getElementById("emptyMovements");
const movementsTableWrapper =
    document.getElementById("movementsTableWrapper");

let currentSku = null;
let currentInventory = null;


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


function setLoading(button, loading, loadingText) {
    if (!button.dataset.originalText) {
        button.dataset.originalText = button.textContent;
    }

    button.disabled = loading;
    button.textContent = loading
        ? loadingText
        : button.dataset.originalText;
}


async function readJson(response) {
    const result = await response.json().catch(() => null);

    if (!result) {
        throw new Error("服务器没有返回有效数据");
    }

    return result;
}


function movementTypeText(type) {
    const values = {
        inbound: "商品入库",
        sale: "销售出库",
        return: "销售退货",
        reversal: "销售冲销",
        adjustment: "库存校正"
    };

    return values[type] || type || "-";
}


function updateCorrectionPreview() {
    if (!currentInventory) {
        return;
    }

    const change = Number(quantityChangeInput.value);
    const beforeQuantity = Number(currentInventory.on_hand_qty || 0);
    const afterQuantity = beforeQuantity + change;

    const preview = document.getElementById("correctionPreview");

    if (!Number.isInteger(change) || change === 0) {
        preview.textContent = "请输入不等于 0 的整数";
        preview.classList.add("negative");
        return;
    }

    preview.textContent =
        `当前 ${beforeQuantity} 双 → 校正后 ${afterQuantity} 双`;

    preview.classList.toggle("negative", afterQuantity < 0);

    if (change > 0) {
        correctionReason.value = "missed_scan";
    } else {
        correctionReason.value = "duplicate_scan";
    }
}


function renderProduct() {
    document.getElementById("productLocalSku").textContent =
        currentSku.local_sku || "-";

    document.getElementById("productStatus").textContent =
        currentSku.status || "-";

    document.getElementById("productName").textContent =
        `${currentSku.brand} ${currentSku.article_number} ${currentSku.size}`;

    document.getElementById("productBarcode").textContent =
        currentSku.barcode || "-";

    document.getElementById("onHandQuantity").textContent =
        currentInventory.on_hand_qty ?? 0;

    document.getElementById("averageCost").textContent =
        money(currentInventory.avg_cost);

    document.getElementById("inventoryValue").textContent =
        money(
            Number(currentInventory.on_hand_qty || 0) *
            Number(currentInventory.avg_cost || 0)
        );

    updateCorrectionPreview();
}


function renderMovements(movements) {
    movementsBody.innerHTML = "";

    if (!Array.isArray(movements) || movements.length === 0) {
        emptyMovements.classList.remove("hidden");
        movementsTableWrapper.classList.add("hidden");
        return;
    }

    emptyMovements.classList.add("hidden");
    movementsTableWrapper.classList.remove("hidden");

    movements.forEach(movement => {
        const row = document.createElement("tr");
        const quantity = Number(movement.quantity_change || 0);

        const quantityClass = quantity >= 0
            ? "quantity-positive"
            : "quantity-negative";

        const quantityText = quantity > 0
            ? `+${quantity}`
            : String(quantity);

        row.innerHTML = `
            <td>${escapeHtml(movement.created_at || "-")}</td>

            <td>
                <span class="movement-badge">
                    ${escapeHtml(movementTypeText(movement.movement_type))}
                </span>
            </td>

            <td class="${quantityClass}">
                ${quantityText}
            </td>

            <td>${movement.before_qty ?? "-"}</td>
            <td>${movement.after_qty ?? "-"}</td>
            <td>${money(movement.unit_cost)}</td>

            <td>
                ${escapeHtml(movement.reference_no || "-")}
            </td>

            <td>
                ${escapeHtml(movement.note || "-")}
            </td>
        `;

        movementsBody.appendChild(row);
    });
}


async function loadInventory() {
    const response = await fetch(
        `/api/v1/inventory/${encodeURIComponent(currentSku.local_sku)}`
    );

    const result = await readJson(response);

    if (!response.ok) {
        throw new Error(result.message || "库存查询失败");
    }

    currentInventory = result.data;
    renderProduct();
}


async function loadMovements() {
    if (!currentSku) {
        return;
    }

    setLoading(
        refreshMovementsButton,
        true,
        "刷新中……"
    );

    try {
        const response = await fetch(
            `/api/v1/inventory/` +
            `${encodeURIComponent(currentSku.local_sku)}/movements`
        );

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "库存流水查询失败");
        }

        renderMovements(result.data);
    } catch (error) {
        showMessage(error.message || "库存流水查询失败");
    } finally {
        setLoading(
            refreshMovementsButton,
            false,
            "刷新中……"
        );
    }
}


async function searchProduct() {
    const barcode = barcodeInput.value.trim();

    hideMessage();
    productSection.classList.add("hidden");
    currentSku = null;
    currentInventory = null;

    if (!barcode) {
        showMessage("请先扫描或输入条码");
        barcodeInput.focus();
        return;
    }

    setLoading(searchButton, true, "查询中……");

    try {
        const skuResponse = await fetch(
            `/api/v1/skus/barcode/${encodeURIComponent(barcode)}`
        );

        const skuResult = await readJson(skuResponse);

        if (!skuResponse.ok) {
            if (skuResponse.status === 404) {
                throw new Error(
                    "该条码尚未建立 SKU，请先前往扫码入库页面补录"
                );
            }

            throw new Error(skuResult.message || "商品查询失败");
        }

        currentSku = skuResult.data;

        await loadInventory();
        await loadMovements();

        productSection.classList.remove("hidden");
        showMessage("商品和库存流水查询成功", "info");
    } catch (error) {
        showMessage(error.message || "商品查询失败");
    } finally {
        setLoading(searchButton, false, "查询中……");
    }
}


async function submitCorrection() {
    if (!currentSku || !currentInventory) {
        showMessage("请先查询商品");
        return;
    }

    const quantityChange = Number(quantityChangeInput.value);
    const beforeQuantity = Number(currentInventory.on_hand_qty || 0);
    const afterQuantity = beforeQuantity + quantityChange;
    const note = document.getElementById("correctionNote").value.trim();

    if (!Number.isInteger(quantityChange) || quantityChange === 0) {
        showMessage("库存变化必须是不等于 0 的整数");
        return;
    }

    if (afterQuantity < 0) {
        showMessage(
            `当前只有 ${beforeQuantity} 双，库存不能减少到负数`
        );
        return;
    }

    if (!note) {
        showMessage("请填写库存校正备注");
        return;
    }

    const confirmed = window.confirm(
        `确定修改库存吗？\n\n` +
        `当前库存：${beforeQuantity} 双\n` +
        `数量变化：${quantityChange > 0 ? "+" : ""}${quantityChange} 双\n` +
        `校正后库存：${afterQuantity} 双`
    );

    if (!confirmed) {
        return;
    }

    const payload = {
        local_sku: currentSku.local_sku,
        quantity_change: quantityChange,
        reason: correctionReason.value,
        note: note
    };

    hideMessage();
    setLoading(
        submitCorrectionButton,
        true,
        "正在校正……"
    );

    try {
        const response = await fetch(
            "/api/v1/inventory/corrections",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            }
        );

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "库存校正失败");
        }

        await loadInventory();
        await loadMovements();

        document.getElementById("correctionNote").value = "";
        quantityChangeInput.value = "1";
        updateCorrectionPreview();

        showMessage(
            `库存校正成功，当前库存为 ` +
            `${currentInventory.on_hand_qty} 双`,
            "info"
        );
    } catch (error) {
        showMessage(error.message || "库存校正失败");
    } finally {
        setLoading(
            submitCorrectionButton,
            false,
            "正在校正……"
        );
    }
}


minusButton.addEventListener("click", () => {
    quantityChangeInput.value = "-1";
    updateCorrectionPreview();
});

plusButton.addEventListener("click", () => {
    quantityChangeInput.value = "1";
    updateCorrectionPreview();
});

quantityChangeInput.addEventListener(
    "input",
    updateCorrectionPreview
);

searchButton.addEventListener("click", searchProduct);
submitCorrectionButton.addEventListener("click", submitCorrection);
refreshMovementsButton.addEventListener("click", loadMovements);

barcodeInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
        event.preventDefault();
        searchProduct();
    }
});

window.addEventListener("DOMContentLoaded", () => {
    barcodeInput.focus();
});