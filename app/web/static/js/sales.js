const barcodeInput = document.getElementById("barcodeInput");
const addButton = document.getElementById("addButton");
const submitSaleButton = document.getElementById("submitSaleButton");
const continueButton = document.getElementById("continueButton");

const messageBox = document.getElementById("messageBox");
const emptyCart = document.getElementById("emptyCart");
const cartTableWrapper = document.getElementById("cartTableWrapper");
const cartBody = document.getElementById("cartBody");
const successCard = document.getElementById("successCard");

let cart = [];


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


function calculateTotals() {
    const quantity = cart.reduce(
        (total, item) => total + item.quantity,
        0
    );

    const amount = cart.reduce(
    (total, item) =>
        total + item.quantity * (item.unitPrice ?? 0),
    0
    );

    return {
        skuCount: cart.length,
        quantity,
        amount
    };
}


function updateSummary() {
    const totals = calculateTotals();

    document.getElementById("cartCount").textContent =
        `${totals.quantity} 双`;

    document.getElementById("summarySkuCount").textContent =
        `${totals.skuCount} 种`;

    document.getElementById("summaryQuantity").textContent =
        `${totals.quantity} 双`;

    document.getElementById("summaryAmount").textContent =
        money(totals.amount);

    const hasMissingPrice = cart.some(
    item => item.unitPrice === null
    );

    submitSaleButton.disabled =
        cart.length === 0 || hasMissingPrice;
}


function renderCart() {
    cartBody.innerHTML = "";

    if (cart.length === 0) {
        emptyCart.classList.remove("hidden");
        cartTableWrapper.classList.add("hidden");
        updateSummary();
        return;
    }

    emptyCart.classList.add("hidden");
    cartTableWrapper.classList.remove("hidden");

    cart.forEach(item => {
        const row = document.createElement("tr");

        row.innerHTML = `
            <td>
                <div class="product-name">
                    <strong>
                        ${escapeHtml(item.brand)}
                        ${escapeHtml(item.articleNumber)}
                    </strong>
                    <span>
                        ${escapeHtml(item.size)}
                        · ${escapeHtml(item.barcode)}
                    </span>
                </div>
            </td>

            <td class="stock-value">
                ${item.availableQty} 双
            </td>

            <td>
                <input
                    class="cart-input quantity-input"
                    type="number"
                    min="1"
                    max="${item.availableQty}"
                    step="1"
                    value="${item.quantity}"
                    data-local-sku="${escapeHtml(item.localSku)}"
                >
            </td>

            <td>
                <input
                    class="cart-input price-input"
                    type="number"
                    min="0"
                    step="0.01"
                    value="${
                        item.unitPrice === null
                            ? ""
                            : Number(item.unitPrice).toFixed(2)
                    }"
                    data-local-sku="${escapeHtml(item.localSku)}"
                >
            </td>

            <td class="subtotal">
                ${
                    item.unitPrice === null
                        ? "待填写"
                        : money(item.quantity * item.unitPrice)
                }
            </td>

            <td>
                <button
                    class="remove-button"
                    type="button"
                    data-local-sku="${escapeHtml(item.localSku)}"
                >
                    删除
                </button>
            </td>
        `;

        cartBody.appendChild(row);
    });

    bindCartEvents();
    updateSummary();
}


function bindCartEvents() {
    document.querySelectorAll(".quantity-input").forEach(input => {
        input.addEventListener("change", event => {
            const localSku = event.target.dataset.localSku;
            const item = cart.find(row => row.localSku === localSku);
            const quantity = Number(event.target.value);

            if (!item) {
                return;
            }

            if (
                !Number.isInteger(quantity) ||
                quantity < 1 ||
                quantity > item.availableQty
            ) {
                showMessage(
                    `销售数量必须在 1 到 ${item.availableQty} 之间`
                );

                event.target.value = item.quantity;
                return;
            }

            item.quantity = quantity;
            hideMessage();
            renderCart();
        });
    });

    document.querySelectorAll(".price-input").forEach(input => {
    input.addEventListener("change", event => {
        const localSku = event.target.dataset.localSku;
        const item = cart.find(
            row => row.localSku === localSku
        );

        if (!item) {
            return;
        }

        const rawValue = event.target.value.trim();

        if (rawValue === "") {
            item.unitPrice = null;
            hideMessage();
            renderCart();
            return;
        }

        const unitPrice = Number(rawValue);

        if (!Number.isFinite(unitPrice) || unitPrice < 0) {
            showMessage("实际成交价不能小于 0");

            event.target.value =
                item.unitPrice === null
                    ? ""
                    : item.unitPrice.toFixed(2);

            return;
        }

        item.unitPrice = unitPrice;
        hideMessage();
        renderCart();
    });
});

    document.querySelectorAll(".remove-button").forEach(button => {
        button.addEventListener("click", event => {
            const localSku = event.target.dataset.localSku;

            cart = cart.filter(
                item => item.localSku !== localSku
            );

            hideMessage();
            renderCart();
            barcodeInput.focus();
        });
    });
}


async function addProduct() {
    const barcode = barcodeInput.value.trim();

    hideMessage();

    if (!barcode) {
        showMessage("请先扫描或输入条码");
        barcodeInput.focus();
        return;
    }

    setLoading(addButton, true, "查询中……");

    try {
        const skuResponse = await fetch(
            `/api/v1/skus/barcode/${encodeURIComponent(barcode)}`
        );

        const skuResult = await readJson(skuResponse);

        if (!skuResponse.ok) {
            if (skuResponse.status === 404) {
                throw new Error(
                    "该条码尚未建立 SKU，请先前往扫码入库页面补录商品"
                );
            }

            throw new Error(skuResult.message || "商品查询失败");
        }

        const sku = skuResult.data;

        if (sku.status !== "active") {
            throw new Error("该 SKU 当前不是启用状态，不能销售");
        }

        const inventoryResponse = await fetch(
            `/api/v1/inventory/${encodeURIComponent(sku.local_sku)}`
        );

        const inventoryResult = await readJson(inventoryResponse);

        if (!inventoryResponse.ok) {
            throw new Error(
                inventoryResult.message || "库存查询失败"
            );
        }

        const availableQty = Number(
            inventoryResult.data.available_qty ?? 0
        );

        if (availableQty <= 0) {
            throw new Error("该商品当前没有可销售库存");
        }

        const existingItem = cart.find(
            item => item.localSku === sku.local_sku
        );

        if (existingItem) {
            if (existingItem.quantity >= availableQty) {
                throw new Error(
                    `该商品最多只能销售 ${availableQty} 双`
                );
            }

            existingItem.quantity += 1;
        } else {
            cart.push({
                localSku: sku.local_sku,
                barcode: sku.barcode,
                brand: sku.brand,
                articleNumber: sku.article_number,
                size: sku.size,
                availableQty,
                quantity: 1,
                unitPrice: null
            });
        }

        barcodeInput.value = "";

        showMessage(
            `${sku.brand} ${sku.article_number} ${sku.size} 已加入销售清单`,
            "info"
        );

        renderCart();
        barcodeInput.focus();
    } catch (error) {
        showMessage(error.message || "商品加入失败");
    } finally {
        setLoading(addButton, false, "查询中……");
    }
}


async function submitSale() {
    if (cart.length === 0) {
        showMessage("销售清单不能为空");
        return;
    }

    const invalidItem = cart.find(item =>
        !Number.isInteger(item.quantity) ||
        item.quantity <= 0 ||
        item.quantity > item.availableQty ||
        !Number.isFinite(item.unitPrice) ||
        item.unitPrice < 0
    );

    if (invalidItem) {
        showMessage(
            "请检查销售数量，并为每件商品填写实际成交价"
        );
        return;
    }

    const payload = {
        items: cart.map(item => ({
            local_sku: item.localSku,
            quantity: item.quantity,
            unit_price: item.unitPrice
        })),
        note: document.getElementById("saleNote").value.trim() || null
    };

    hideMessage();
    setLoading(submitSaleButton, true, "正在完成销售……");

    try {
        const response = await fetch("/api/v1/sales", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "销售失败");
        }

        const sale = result.data;
        const totals = calculateTotals();

        document.querySelector(".sales-layout").classList.add("hidden");
        successCard.classList.remove("hidden");

        document.getElementById("successText").textContent =
            `本次共销售 ${totals.quantity} 双，` +
            `销售金额 ${money(totals.amount)}。`;

        document.getElementById("saleNumber").textContent =
            `销售单号：${sale.sale_no || "-"}`;

        hideMessage();
    } catch (error) {
        showMessage(error.message || "销售失败");
        submitSaleButton.disabled = false;
    } finally {
        setLoading(
            submitSaleButton,
            false,
            "正在完成销售……"
        );

        if (cart.length > 0) {
            submitSaleButton.disabled = false;
        }
    }
}


function resetSale() {
    cart = [];

    barcodeInput.value = "";
    document.getElementById("saleNote").value = "";

    successCard.classList.add("hidden");
    document.querySelector(".sales-layout").classList.remove("hidden");

    hideMessage();
    renderCart();
    barcodeInput.focus();
}


addButton.addEventListener("click", addProduct);
submitSaleButton.addEventListener("click", submitSale);
continueButton.addEventListener("click", resetSale);

barcodeInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
        event.preventDefault();
        addProduct();
    }
});

window.addEventListener("DOMContentLoaded", () => {
    renderCart();
    barcodeInput.focus();
});