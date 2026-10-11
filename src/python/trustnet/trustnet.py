"""Fetch the public Trustnet IA Unit Trusts & OEICs performance table."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

TRUSTNET_URL = (
    "https://www.trustnet.com/fund/price-performance/o/ia-unit-trusts-and-oeics"
)
SEARCH_URL = "https://www.trustnet.com/umbraco/surface/search/SearchFunds"
PERIODS = {
    "1y": {"label": "1 year", "sort": "P11GBP_D_12M", "field": "one_year_return"},
    "3y": {"label": "3 years", "sort": "P11GBP_D_36M", "field": "three_year_return"},
    "5y": {"label": "5 years", "sort": "P11GBP_D_60M", "field": "five_year_return"},
}
PAGE_SIZE = 75
ETF_NAME = re.compile(r"\bETF\b|exchange[- ]traded fund", re.IGNORECASE)
PASSIVE_NAME = re.compile(
    r"\b(passive|tracker|tracking|index(?![- ]linked))\b", re.IGNORECASE
)
ACTIVE_NAME_EXCEPTION = re.compile(
    r"\b(enhanced index|research enhanced index|index opportunities)\b",
    re.IGNORECASE,
)


class TrustnetError(RuntimeError):
    """Raised when Trustnet does not provide a usable performance table."""


@dataclass(frozen=True)
class Fund:
    name: str
    management_style: str
    five_year_return: float | None = None
    one_year_return: float | None = None
    three_year_return: float | None = None
    asset_class: str = ""
    factsheet_url: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_return(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", "").replace("%", "")
    if not cleaned or cleaned in {"-", "--", "N/A"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _management_style_from_name(name: str) -> str:
    if ACTIVE_NAME_EXCEPTION.search(name):
        return "active"
    return "passive" if PASSIVE_NAME.search(name) else "active"


def _parse_fund_rows(html: str) -> list[Fund]:
    soup = BeautifulSoup(html, "html.parser")
    funds: list[Fund] = []

    for row in soup.select("tr.fe-fundrows"):
        name_link = row.select_one('td[data-column="Name"] a')
        if name_link is None:
            continue

        name = name_link.get_text(" ", strip=True)
        if not name or ETF_NAME.search(name):
            continue

        five_year_cell = row.select_one('td[data-column="DiscretePerf60Months"]')
        one_year_cell = row.select_one('td[data-column="DiscretePerf12Months"]')
        three_year_cell = row.select_one('td[data-column="DiscretePerf36Months"]')
        asset_class_cell = row.select_one('td[data-column="AssetClass"]')
        factsheet_path = name_link.get("href", "")

        funds.append(
            Fund(
                name=name,
                management_style=_management_style_from_name(name),
                five_year_return=(
                    _parse_return(five_year_cell.get_text(" ", strip=True))
                    if five_year_cell
                    else None
                ),
                one_year_return=(
                    _parse_return(one_year_cell.get_text(" ", strip=True))
                    if one_year_cell
                    else None
                ),
                three_year_return=(
                    _parse_return(three_year_cell.get_text(" ", strip=True))
                    if three_year_cell
                    else None
                ),
                asset_class=(
                    asset_class_cell.get_text(" ", strip=True)
                    if asset_class_cell
                    else ""
                ),
                factsheet_url=urljoin(TRUSTNET_URL, factsheet_path),
            )
        )

    return funds


def _fetch_page(
    session: requests.Session,
    token: str,
    page: int,
    page_size: int,
    sort_key: str,
) -> tuple[list[Fund], int]:
    payload = [
        ("OrderBy", sort_key),
        ("Asc", "desc"),
        ("ColumnSet", "FundOverview"),
        ("Page", str(page)),
        ("PopulateFiltersFromFacets", "True"),
        ("IsPdfExport", "True"),
        ("IsFilterApplied", "True"),
        ("IsTabClicked", "False"),
        ("FundUniverse", "O"),
        ("NoRiskScore", "true"),
        ("RiskScore", "0,1000"),
        ("Keywords", ""),
        ("Page", str(page)),
        ("PageSize", str(page_size)),
        ("X-Requested-With", "XMLHttpRequest"),
        ("__RequestVerificationToken", token),
    ]
    response = session.post(
        SEARCH_URL,
        data=payload,
        headers={
            "Referer": TRUSTNET_URL,
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=(5, 25),
    )
    response.raise_for_status()
    row_count = len(BeautifulSoup(response.text, "html.parser").select("tr.fe-fundrows"))
    return _parse_fund_rows(response.text), row_count


def fetch_top_funds(
    limit: int = 50,
    period: str = "5y",
    management: str = "all",
) -> list[dict[str, Any]]:
    """Return the highest Trustnet unit-trust returns for a selected period."""
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    if period not in PERIODS:
        raise ValueError(f"Unsupported period {period!r}; choose 1y, 3y, or 5y.")
    if management not in {"active", "passive", "all"}:
        raise ValueError("management must be active, passive, or all.")

    period_config = PERIODS[period]
    sort_key = period_config["sort"]

    listing_url = (
        f"{TRUSTNET_URL}?norisk=true&sortby={sort_key}"
        f"&sortorder=desc&PageSize={PAGE_SIZE}"
    )
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "LocalTrustnetPerformanceViewer/1.0 (personal-use)",
            "Accept": "text/html,application/xhtml+xml",
        }
    )

    try:
        listing = session.get(listing_url, timeout=(5, 25))
        listing.raise_for_status()
        token_input = BeautifulSoup(listing.text, "html.parser").select_one(
            'input[name="__RequestVerificationToken"]'
        )
        token = token_input.get("value", "") if token_input else ""
        if not token:
            raise TrustnetError("Trustnet did not provide its request token.")

        funds: list[Fund] = []
        seen: set[str] = set()
        for page in range(10):
            page_funds, row_count = _fetch_page(
                session, token, page, PAGE_SIZE, sort_key
            )
            for fund in page_funds:
                if (
                    getattr(fund, period_config["field"]) is not None
                    and (
                        management == "all"
                        or fund.management_style == management
                    )
                    and fund.factsheet_url not in seen
                ):
                    seen.add(fund.factsheet_url)
                    funds.append(fund)
            if len(funds) >= limit or row_count < PAGE_SIZE:
                break

        funds.sort(
            key=lambda fund: getattr(fund, period_config["field"]),
            reverse=True,
        )
        return [fund.as_dict() for fund in funds[:limit]]
    except requests.RequestException as exc:
        raise TrustnetError(f"Could not retrieve Trustnet performance data: {exc}") from exc
