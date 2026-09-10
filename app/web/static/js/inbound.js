const barcodeInput = document.getElementById("barcodeInput");
const searchButton = document.getElementById("searchButton");
const createSkuButton = document.getElementById("createSkuButton");
const inboundButton = document.getElementById("inboundButton");
const resetButton = document.getElementById("resetButton");
const continueButton = document.getElementById("continueButton");

const skuResultCard = document.getElementById("skuResultCard");
const manualSkuCard = document.getElementById("manualSkuCard");
const inboundCard = document.getElementById("inboundCard");
const successCard = document.getElementById("successCard");
const messageBox = document.getElementById("messageBox");

let currentSku = null;


function showMessage(message, type = "error") {
    messageBox.textContent = message;
    messageBox.className = `message-box ${type}`;
}


function hideMessage() {
    messageBox.textContent = "";
    messageBox.className = "message-box hidden";
}


function money(value) {
    return `¥${Number(value || 0).toFixed(2)}`;
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


function displaySku(sku) {
    currentSku = sku;

    document.getElementById("skuLocalSku").textContent =
        sku.local_sku || "-";
    document.getElementById("skuBarcode").textContent =
        sku.barcode || "-";
    document.getElementById("skuBrand").textContent =
        sku.brand || "-";
    document.getElementById("skuArticleNumber").textContent =
        sku.article_number || "-";
    document.getElementById("skuSize").textContent =
        sku.size || "-";


    manualSkuCard.classList.add("hidden");
    skuResultCard.classList.remove("hidden");
    inboundCard.classList.remove("hidden");

    document.getElementById("inboundQuantity").focus();
}


async function searchBarcode() {
    const barcode = barcodeInput.value.trim();

    hideMessage();
    skuResultCard.classList.add("hidden");
    manualSkuCard.classList.add("hidden");
    inboundCard.classList.add("hidden");
    successCard.classList.add("hidden");
    currentSku = null;

    if (!barcode) {
        showMessage("请先扫描或输入条码");
        barcodeInput.focus();
        return;
    }

    setLoading(searchButton, true, "查询中……");

    try {
        const response = await fetch(
            `/api/v1/skus/barcode/${encodeURIComponent(barcode)}`
        );
        const result = await readJson(response);

        if (response.ok) {
            displaySku(result.data);
            showMessage("已经找到商品，可以填写本次入库信息", "info");
            return;
        }

        if (response.status === 404) {
            document.getElementById("manualBarcode").value = barcode;
            manualSkuCard.classList.remove("hidden");
            showMessage(
                "这是该条码第一次入库，请先填写品牌、货号和尺码",
                "info"
            );
            document.getElementById("manualBrand").focus();
            return;
        }

        throw new Error(result.message || "条码查询失败");
    } catch (error) {
        showMessage(error.message || "无法连接服务器");
    } finally {
        setLoading(searchButton, false, "查询中……");
    }
}


async function createSku() {
    const payload = {
    barcode: document.getElementById("manualBarcode").value.trim(),
    brand: document.getElementById("manualBrand").value.trim(),
    article_number:
        document.getElementById("manualArticleNumber").value.trim(),
    size: document.getElementById("manualSize").value.trim(),
    status: "active"
    };

    if (!payload.brand || !payload.article_number || !payload.size) {
        showMessage("品牌、货号和尺码都必须填写");
        return;
    }



    hideMessage();
    setLoading(createSkuButton, true, "创建中……");

    try {
        const response = await fetch("/api/v1/skus", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "SKU 创建失败");
        }

        displaySku(result.data);
        showMessage("SKU 创建成功，请继续填写入库信息", "info");
    } catch (error) {
        showMessage(error.message || "SKU 创建失败");
    } finally {
        setLoading(createSkuButton, false, "创建中……");
    }
}


async function submitInbound() {
    if (!currentSku) {
        showMessage("请先扫描并确认商品");
        return;
    }

    const quantity =
        Number(document.getElementById("inboundQuantity").value);
    const unitCost =
        Number(document.getElementById("inboundUnitCost").value);

    if (!Number.isInteger(quantity) || quantity <= 0) {
        showMessage("入库数量必须是大于 0 的整数");
        return;
    }

    if (!Number.isFinite(unitCost) || unitCost < 0) {
        showMessage("请填写正确的本次单件成本");
        return;
    }

    const payload = {
        local_sku: currentSku.local_sku,
        quantity: quantity,
        unit_cost: unitCost,
        reference_no:
            document.getElementById("inboundReferenceNo").value.trim() || null,
        note:
            document.getElementById("inboundNote").value.trim() || null
    };

    hideMessage();
    setLoading(inboundButton, true, "正在入库……");

    try {
        const response = await fetch("/api/v1/inventory/inbounds", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "入库失败");
        }

        const data = result.data;

        skuResultCard.classList.add("hidden");
        manualSkuCard.classList.add("hidden");
        inboundCard.classList.add("hidden");
        successCard.classList.remove("hidden");

        document.getElementById("successText").textContent =
            `${currentSku.brand} ${currentSku.article_number} ` +
            `${currentSku.size}，本次入库 ${quantity} 双，` +
            `单件成本 ${money(unitCost)}。` +
            `入库后库存：${data.after_qty ?? "已更新"} 双。`;

        hideMessage();
    } catch (error) {
        showMessage(error.message || "入库失败");
    } finally {
        setLoading(inboundButton, false, "正在入库……");
    }
}


function resetPage() {
    currentSku = null;

    barcodeInput.value = "";
    document.getElementById("manualBarcode").value = "";
    document.getElementById("manualBrand").value = "";
    document.getElementById("manualArticleNumber").value = "";
    document.getElementById("manualSize").value = "";

    document.getElementById("inboundQuantity").value = "1";
    document.getElementById("inboundUnitCost").value = "";
    document.getElementById("inboundReferenceNo").value = "";
    document.getElementById("inboundNote").value = "";

    skuResultCard.classList.add("hidden");
    manualSkuCard.classList.add("hidden");
    inboundCard.classList.add("hidden");
    successCard.classList.add("hidden");

    hideMessage();
    barcodeInput.focus();
}


searchButton.addEventListener("click", searchBarcode);
createSkuButton.addEventListener("click", createSku);
inboundButton.addEventListener("click", submitInbound);
resetButton.addEventListener("click", resetPage);
continueButton.addEventListener("click", resetPage);

barcodeInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
        event.preventDefault();
        searchBarcode();
    }
});

window.addEventListener("DOMContentLoaded", () => {
    barcodeInput.focus();
});