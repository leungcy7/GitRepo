const rows = document.querySelector("#fund-rows");
const statusLine = document.querySelector("#status");
const updatedAt = document.querySelector("#updated-at");
const refreshButton = document.querySelector("#refresh-button");
const rankedOn = document.querySelector("#ranked-on");
const periodSelect = document.querySelector("#period-select");
const managementSelect = document.querySelector("#management-select");
let selectedPeriod = periodSelect.value;
let selectedManagement = managementSelect.value;

const periodLabels = {
    "1y": "1 year",
    "3y": "3 years",
    "5y": "5 years",
};

function formatReturn(value) {
    if (value === null || value === undefined) return "—";
    return `${new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 }).format(value)}%`;
}

function returnClass(value) {
    if (value === null || value === undefined) return "return-col";
    return `return-col ${value < 0 ? "negative" : "positive"}`;
}

function renderFunds(funds) {
    rows.replaceChildren();
    if (!funds.length) {
        const emptyRow = document.createElement("tr");
        const emptyCell = document.createElement("td");
        emptyCell.className = "empty-state";
        emptyCell.colSpan = 7;
        emptyCell.textContent = "No funds available for this period.";
        emptyRow.append(emptyCell);
        rows.append(emptyRow);
        rankedOn.textContent = `${periodLabels[selectedPeriod]} return (%)`;
        return;
    }

    funds.forEach((fund, index) => {
        const row = document.createElement("tr");
        const rank = document.createElement("td");
        rank.className = "rank-cell";
        rank.textContent = String(index + 1).padStart(2, "0");

        const nameCell = document.createElement("td");
        const link = document.createElement("a");
        link.className = "fund-link";
        link.href = fund.factsheet_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = fund.name;
        nameCell.append(link);

        const assetCell = document.createElement("td");
        const assetTag = document.createElement("span");
        assetTag.className = "asset-tag";
        assetTag.textContent = fund.asset_class || "—";
        assetCell.append(assetTag);

        const styleCell = document.createElement("td");
        const styleTag = document.createElement("span");
        styleTag.className = `style-tag ${fund.management_style}`;
        styleTag.textContent = fund.management_style;
        styleCell.append(styleTag);

        const periodReturns = [
            ["1y", fund.one_year_return],
            ["3y", fund.three_year_return],
            ["5y", fund.five_year_return],
        ];
        const returnCells = periodReturns.map(([period, value]) => {
            const cell = document.createElement("td");
            cell.className = `${returnClass(value)}${period === selectedPeriod ? " primary-col" : ""}`;
            cell.dataset.returnPeriod = period;
            cell.textContent = formatReturn(value);
            return cell;
        });

        row.append(rank, nameCell, assetCell, styleCell, ...returnCells);
        rows.append(row);
    });

    document.querySelectorAll("[data-return-period]").forEach((cell) => {
        cell.classList.toggle("primary-col", cell.dataset.returnPeriod === selectedPeriod);
    });
    rankedOn.textContent = `${periodLabels[selectedPeriod]} return (%)`;
}

async function loadFunds() {
    refreshButton.disabled = true;
    statusLine.classList.remove("error");
    statusLine.textContent = "Loading Trustnet performance data...";
    try {
        const params = new URLSearchParams({
            period: selectedPeriod,
            management: selectedManagement,
        });
        const response = await fetch(`/api/funds?${params}`, { cache: "no-store" });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Trustnet request failed.");
        renderFunds(result.funds);
        updatedAt.textContent = new Date(result.fetched_at).toLocaleString();
        const managementLabel = selectedManagement === "all" ? "funds" : `${selectedManagement} funds`;
        if (!result.funds.length) {
            statusLine.textContent = `No ${managementLabel} available for ${periodLabels[selectedPeriod]} return.`;
        } else {
            statusLine.textContent = `${result.funds.length} ${managementLabel} · sorted by ${periodLabels[selectedPeriod]} return, highest first`;
        }
    } catch (error) {
        rows.innerHTML = '<tr><td class="empty-state" colspan="7">No results available.</td></tr>';
        statusLine.classList.add("error");
        statusLine.textContent = error.message || "Could not load Trustnet data.";
    } finally {
        refreshButton.disabled = false;
    }
}

refreshButton.addEventListener("click", loadFunds);
periodSelect.addEventListener("change", () => {
    selectedPeriod = periodSelect.value;
    loadFunds();
});
managementSelect.addEventListener("change", () => {
    selectedManagement = managementSelect.value;
    loadFunds();
});
loadFunds();
