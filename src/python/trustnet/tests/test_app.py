import pytest
from fastapi.testclient import TestClient

import main
import trustnet as trustnet_module
from trustnet import (
    Fund,
    TrustnetError,
    _management_style_from_name,
    _parse_fund_rows,
    fetch_top_funds,
)

client = TestClient(main.app)


def test_parser_extracts_performance_and_factsheet_link():
    html = """
    <table><tbody>
      <tr class="fe-fundrows">
        <td data-column="Name"><a href="/factsheets/O/AB12/sample-fund">Sample Fund</a></td>
        <td data-column="AssetClass">EQ</td>
        <td data-column="DiscretePerf12Months">12.5</td>
        <td data-column="DiscretePerf36Months">31.2</td>
        <td data-column="DiscretePerf60Months">87.6</td>
      </tr>
    </tbody></table>
    """

    funds = _parse_fund_rows(html)

    assert len(funds) == 1
    assert funds[0].name == "Sample Fund"
    assert funds[0].management_style == "active"
    assert funds[0].five_year_return == 87.6
    assert funds[0].one_year_return == 12.5
    assert funds[0].three_year_return == 31.2
    assert funds[0].asset_class == "EQ"
    assert funds[0].factsheet_url.endswith("/factsheets/O/AB12/sample-fund")


def test_parser_skips_etfs_but_preserves_missing_period_values():
    html = """
    <table><tbody>
      <tr class="fe-fundrows">
        <td data-column="Name"><a href="/etf">Example UCITS ETF</a></td>
        <td data-column="DiscretePerf60Months">99.0</td>
      </tr>
      <tr class="fe-fundrows">
        <td data-column="Name"><a href="/fund">No Five Year Data</a></td>
        <td data-column="DiscretePerf60Months">-</td>
      </tr>
            <tr class="fe-fundrows">
                <td data-column="Name"><a href="/index">Example Index Fund</a></td>
                <td data-column="DiscretePerf60Months">33.0</td>
            </tr>
    </tbody></table>
    """

    funds = _parse_fund_rows(html)

    assert len(funds) == 2
    assert funds[0].name == "No Five Year Data"
    assert funds[0].five_year_return is None
    assert funds[0].management_style == "active"
    assert funds[1].management_style == "passive"


def test_management_style_name_rules_handle_index_opportunities():
    assert _management_style_from_name("L&G Global Technology Index Trust") == "passive"
    assert _management_style_from_name("Equity Tracker Fund") == "passive"
    assert _management_style_from_name("Inst Asia Pacific Index Opportunities") == "active"
    assert _management_style_from_name("Research Enhanced Index Equity") == "active"


def test_fetcher_uses_raw_rows_to_continue_pagination(monkeypatch):
    class ListingResponse:
        text = '<input name="__RequestVerificationToken" value="token">'

        @staticmethod
        def raise_for_status():
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {}

        @staticmethod
        def get(*args, **kwargs):
            return ListingResponse()

    def make_fund(index):
        return Fund(
            name=f"Fund {index}",
            management_style="active",
            five_year_return=float(100 - index),
            one_year_return=None,
            three_year_return=None,
            asset_class="EQ",
            factsheet_url=f"https://www.trustnet.com/factsheets/{index}",
        )

    page_calls = []

    def fetch_page(session, token, page, page_size, sort_key):
        page_calls.append(page)
        assert sort_key == "P11GBP_D_60M"
        if page == 0:
            return [make_fund(0)], page_size
        return [make_fund(index) for index in range(1, 50)], 50

    monkeypatch.setattr(trustnet_module.requests, "Session", FakeSession)
    monkeypatch.setattr(trustnet_module, "_fetch_page", fetch_page)

    funds = fetch_top_funds()

    assert len(funds) == 50
    assert page_calls == [0, 1]


@pytest.mark.parametrize(
    ("period", "sort_key", "expected_names"),
    [
        ("1y", "P11GBP_D_12M", ["One-year leader", "Other fund"]),
        ("3y", "P11GBP_D_36M", ["Three-year leader", "One-year leader"]),
        ("5y", "P11GBP_D_60M", ["Five-year leader", "Other fund"]),
    ],
)
def test_fetcher_sorts_by_selected_period(monkeypatch, period, sort_key, expected_names):
    class ListingResponse:
        text = '<input name="__RequestVerificationToken" value="token">'

        @staticmethod
        def raise_for_status():
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {}

        @staticmethod
        def get(*args, **kwargs):
            return ListingResponse()

    funds_by_name = [
        Fund(
            name="Other fund",
            management_style="active",
            five_year_return=95,
            one_year_return=90,
            three_year_return=10,
            asset_class="EQ",
            factsheet_url="https://www.trustnet.com/factsheets/other",
        ),
        Fund(
            name="One-year leader",
            management_style="active",
            five_year_return=20,
            one_year_return=99,
            three_year_return=20,
            asset_class="EQ",
            factsheet_url="https://www.trustnet.com/factsheets/one-year",
        ),
        Fund(
            name="Three-year leader",
            management_style="active",
            five_year_return=30,
            one_year_return=10,
            three_year_return=99,
            asset_class="EQ",
            factsheet_url="https://www.trustnet.com/factsheets/three-year",
        ),
        Fund(
            name="Five-year leader",
            management_style="active",
            five_year_return=99,
            one_year_return=20,
            three_year_return=20,
            asset_class="EQ",
            factsheet_url="https://www.trustnet.com/factsheets/five-year",
        ),
    ]
    requested_sort_keys = []

    def fetch_page(session, token, page, page_size, requested_sort_key):
        requested_sort_keys.append(requested_sort_key)
        return funds_by_name, len(funds_by_name)

    monkeypatch.setattr(trustnet_module.requests, "Session", FakeSession)
    monkeypatch.setattr(trustnet_module, "_fetch_page", fetch_page)

    result = fetch_top_funds(limit=2, period=period)

    assert requested_sort_keys == [sort_key]
    assert [fund["name"] for fund in result] == expected_names


def test_api_returns_empty_results_for_missing_period_data(monkeypatch):
    monkeypatch.setattr(main, "fetch_top_funds", lambda *args, **kwargs: [])

    response = client.get("/api/funds?period=1y&management=all")

    assert response.status_code == 200
    assert response.json()["funds"] == []


def test_fetcher_filters_by_management_style(monkeypatch):
    class ListingResponse:
        text = '<input name="__RequestVerificationToken" value="token">'

        @staticmethod
        def raise_for_status():
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {}

        @staticmethod
        def get(*args, **kwargs):
            return ListingResponse()

    funds = [
        Fund(
            name="Managed Growth Fund",
            management_style="active",
            five_year_return=90,
            one_year_return=20,
            three_year_return=50,
            asset_class="EQ",
            factsheet_url="https://www.trustnet.com/factsheets/active",
        ),
        Fund(
            name="Global Equity Index Fund",
            management_style="passive",
            five_year_return=70,
            one_year_return=15,
            three_year_return=40,
            asset_class="EQ",
            factsheet_url="https://www.trustnet.com/factsheets/passive",
        ),
    ]
    monkeypatch.setattr(trustnet_module.requests, "Session", FakeSession)
    monkeypatch.setattr(
        trustnet_module,
        "_fetch_page",
        lambda session, token, page, page_size, sort_key: (funds, len(funds)),
    )

    result = fetch_top_funds(limit=10, management="passive")

    assert [fund["name"] for fund in result] == ["Global Equity Index Fund"]


def test_homepage_serves_dashboard():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Fund performance leaders" in response.text
    assert 'id="period-select"' in response.text
    assert 'value="1y"' in response.text
    assert 'value="3y"' in response.text
    assert 'value="5y"' in response.text
    assert 'value="10y"' not in response.text
    assert 'value="5y" selected' in response.text
    assert 'id="management-select"' in response.text
    assert 'value="active"' in response.text
    assert 'value="passive"' in response.text
    assert 'value="all" selected' in response.text
    assert "/static/styles.css" in response.text


def test_api_returns_ranked_funds(monkeypatch):
    expected = [
        {
            "name": "Sample Fund",
            "management_style": "active",
            "five_year_return": 87.6,
            "one_year_return": 12.5,
            "three_year_return": 31.2,
            "asset_class": "EQ",
            "factsheet_url": "https://www.trustnet.com/factsheets/sample-fund",
        }
    ]
    calls = []

    def fake_fetch(limit, period, management):
        calls.append((limit, period, management))
        return expected

    monkeypatch.setattr(main, "fetch_top_funds", fake_fetch)

    response = client.get("/api/funds?period=3y&management=passive")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "3y"
    assert body["period_label"] == "3 years"
    assert body["management"] == "passive"
    assert body["funds"] == expected
    assert calls == [(50, "3y", "passive")]
    assert "fetched_at" in body
    assert "trustnet.com" in body["source_url"]


def test_api_reports_upstream_failure(monkeypatch):
    def fail_fetch(limit, period, management):
        raise TrustnetError("Trustnet is unavailable")

    monkeypatch.setattr(main, "fetch_top_funds", fail_fetch)

    response = client.get("/api/funds")

    assert response.status_code == 502
    assert response.json()["detail"] == "Trustnet is unavailable"


def test_api_rejects_unknown_period():
    response = client.get("/api/funds?period=15y")

    assert response.status_code == 422


def test_api_rejects_unknown_management_style():
    response = client.get("/api/funds?management=hybrid")

    assert response.status_code == 422


def test_stylesheet_is_served():
    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert "--green:" in response.text
