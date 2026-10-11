# Trustnet Fund Performance Leaders

A local FastAPI dashboard that fetches Trustnet's public IA Unit Trusts & OEICs performance table and displays the top 50 funds by reported 1-, 3-, or 5-year return. Choose the ranking period and Active, Passive, or All styles in the dashboard; the defaults are five years and All.

The fetcher requests the table in descending order for the selected period, follows pagination until it has 50 eligible results, excludes entries without a return for that period, and excludes names that explicitly contain `ETF` or `exchange-traded fund`. Trustnet's table response does not provide a separate legal-vehicle or active/passive field. The style filter is therefore an estimate based on name terms such as `Index`, `Tracker`, and `Passive`; it may misclassify funds. `All` retains both styles regardless of the estimate.

## Run locally

```bash
cd /Users/ai_user/trash/src/python/trustnet
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Open <http://127.0.0.1:8000>. The browser dashboard loads its data from `/api/funds`; that endpoint fetches Trustnet when requested. The API accepts `period=1y`, `period=3y`, or `period=5y` and `management=active`, `management=passive`, or `management=all`, for example `/api/funds?period=3y&management=passive`. The JSON endpoint is also useful for inspection or local integrations.

Run tests with:

```bash
python -m pytest -q
```

## Data and use notes

- Returns are percentages as reported in Trustnet's selected performance column. They are cumulative historical performance, not annualized returns.
- Funds can be denominated in different currencies; performance values and ordering follow Trustnet's displayed GBP performance sort for the selected period.
- Results are fetched from Trustnet, not stored locally. The site and its data format can change, so a fetch may need maintenance if Trustnet changes its table.
- Trustnet says its information is for general use, is not investment advice, and must not be relied on for investment decisions. Past performance does not predict future results; investment values and income can fall as well as rise.
- Trustnet's terms restrict reproducing or distributing its content. This app is intended for personal local reference only. Obtain permission or an appropriate licence before sharing or using Trustnet material commercially. Review the current [Trustnet terms](https://www.trustnet.com/information/terms-of-use/) before use.
