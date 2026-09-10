const refreshButton = document.getElementById("refreshButton");
const searchInput = document.getElementById("searchInput");
const statusFilter = document.getElementById("statusFilter");
const skuTableBody = document.getElementById("skuTableBody");
const emptyState = document.getElementById("emptyState");
const messageBox = document.getElementById("messageBox");

let skuRecords = [];


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
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


function normalizeList(data) {
    if (Array.isArray(data)) {
        return data;
    }

    if (Array.isArray(data?.items)) {
        return data.items;
    }

    return [];
}


function statusOptions(currentStatus) {
    const statuses = [
        {
            value: "active",
            label: "启用"
        },
        {
            value: "inactive",
            label: "停用"
        },
        {
            value: "discontinued",
            label: "已停产"
        }
    ];

    return statuses.map(status => `
        <option
            value="${status.value}"
            ${currentStatus === status.value ? "selected" : ""}
        >
            ${status.label}
        </option>
    `).join("");
}


function renderSkus() {
    const keyword = searchInput.value.trim().toLowerCase();
    const selectedStatus = statusFilter.value;

    const filteredRecords = skuRecords.filter(sku => {
        const searchableText = [
            sku.brand,
            sku.article_number,
            sku.size,
            sku.barcode,
            sku.local_sku
        ].join(" ").toLowerCase();

        const matchesKeyword = searchableText.includes(keyword);
        const matchesStatus =
            !selectedStatus || sku.status === selectedStatus;

        return matchesKeyword && matchesStatus;
    });

    skuTableBody.innerHTML = "";

    emptyState.classList.toggle(
        "hidden",
        filteredRecords.length > 0
    );

    filteredRecords.forEach(sku => {
        const row = document.createElement("tr");

        row.innerHTML = `
            <td>${escapeHtml(sku.brand)}</td>

            <td>${escapeHtml(sku.article_number)}</td>

            <td>${escapeHtml(sku.size)}</td>

            <td class="barcode-value">
                ${escapeHtml(sku.barcode || "未绑定条码")}
            </td>

            <td>
                <select
                    class="status-select"
                    data-local-sku="${escapeHtml(sku.local_sku)}"
                >
                    ${statusOptions(sku.status)}
                </select>
            </td>

            <td>
                <button
                    class="save-status-button"
                    type="button"
                    data-local-sku="${escapeHtml(sku.local_sku)}"
                >
                    保存状态
                </button>
            </td>
        `;

        skuTableBody.appendChild(row);
    });

    bindStatusButtons();
}


function bindStatusButtons() {
    document.querySelectorAll(".save-status-button").forEach(button => {
        button.addEventListener("click", async () => {
            const localSku = button.dataset.localSku;

            const select = document.querySelector(
                `.status-select[data-local-sku="${localSku}"]`
            );

            if (!select) {
                return;
            }

            await updateStatus(
                localSku,
                select.value,
                button
            );
        });
    });
}


async function updateStatus(localSku, status, button) {
    hideMessage();

    button.disabled = true;
    button.textContent = "保存中……";

    try {
        const response = await fetch(
            `/api/v1/skus/${encodeURIComponent(localSku)}/status`,
            {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    status: status
                })
            }
        );

        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "状态修改失败");
        }

        const record = skuRecords.find(
            sku => sku.local_sku === localSku
        );

        if (record) {
            record.status = status;
        }

        showMessage(
            `${result.data.brand} ${result.data.article_number} ` +
            `${result.data.size} 的状态已经修改`,
            "info"
        );

        renderSkus();
    } catch (error) {
        showMessage(error.message || "状态修改失败");
        button.disabled = false;
        button.textContent = "保存状态";
    }
}


async function loadSkus() {
    hideMessage();

    refreshButton.disabled = true;
    refreshButton.textContent = "正在刷新……";

    try {
        const response = await fetch("/api/v1/skus");
        const result = await readJson(response);

        if (!response.ok) {
            throw new Error(result.message || "SKU 档案查询失败");
        }

        skuRecords = normalizeList(result.data);

        document.getElementById("skuCount").textContent =
            skuRecords.length;

        renderSkus();
    } catch (error) {
        showMessage(error.message || "SKU 档案查询失败");
    } finally {
        refreshButton.disabled = false;
        refreshButton.textContent = "刷新档案";
    }
}


searchInput.addEventListener("input", renderSkus);
statusFilter.addEventListener("change", renderSkus);
refreshButton.addEventListener("click", loadSkus);

window.addEventListener("DOMContentLoaded", loadSkus);