# Campaign → Search Term Explorer

Streamlit app for drilling into a raw Amazon Sponsored Products **Search Term
report**: expand a campaign to see every search term under it, or expand a
campaign then pick a date to see that day's search term performance.

## What it does

### Scope: FBA portfolios only (excludes Vizari)
Sidebar checkbox **"Only FBA portfolios (excludes Vizari)"**, on by default.
Keeps any portfolio whose name contains "FBA", but always drops any portfolio
that also contains "Vizari" — even if a future portfolio name happened to
contain both.

### Tab 1 — Campaign → Search Terms
Every campaign (after your filters) is a collapsible section. Opening one
shows:
- KPI cards for that campaign (Spend, Sales, ACOS, ROAS) over the selected
  date range
- Every search term that ran under it, aggregated across the date range,
  with Impressions, Clicks, Spend, Sales, Orders, ACOS, ROAS, CVR, CTR
- **ACOS conditional coloring**: below your threshold (default 5%) is light
  green, at/above it — or no sales at all — is light red

### Tab 2 — Campaign → Date → Search Terms
Same campaign list, but opening one gives you a **date picker**. Pick a date
and the search term table refreshes to show only that day's performance for
that campaign, same ACOS coloring.

### Filters (sidebar)
- Date range
- Portfolio multiselect
- Campaign name search — **Contains** or **Starts with** (prefix search)
- ACOS highlight threshold (%) — adjustable, default 5%
- Sort campaigns by Spend / Sales / Clicks / Name
- Max campaigns to display — a responsiveness safeguard. With 300+ campaigns
  possible in a full export, rendering every campaign's expander at once
  would be slow; narrow with the search box or portfolio filter to see more
  of the list, or raise the limit.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```
Open http://localhost:8501 and upload your raw Search Term report (.xlsx) —
the app reads the first sheet, so a multi-sheet workbook (raw data + any
pivot tabs) works fine as long as the raw export is the first sheet.

Expected columns: Date, Portfolio name, Campaign Name, Customer Search Term,
Match Type, Impressions, Clicks, Spend, 7 Day Total Sales, 7 Day Total Orders
— same format as the Amazon Ads console export.

## Hosting on Streamlit Community Cloud

1. Push this folder to a GitHub repo (`app.py` and `requirements.txt` in the
   same directory).
2. Go to https://share.streamlit.io → "New app" → point it at `app.py`.
3. You get a public `*.streamlit.app` link.

If you already have other tools (Placement Intelligence, Search Term
Cannibalization) deployed, this can be a third/fourth page in the same repo
via Streamlit's multipage structure (`pages/search_term_explorer.py`) so
everything shares one URL.

## Notes

- ACOS/ROAS/CTR/CVR are always recomputed from summed Spend/Sales/Clicks/
  Impressions/Orders, never averaged from the report's own row-level ratio
  columns (those go blank on zero-click/zero-sale rows and can't be validly
  averaged).
- A search term with zero sales has no real ACOS (division by zero) — it's
  treated as red in the highlighting, same bucket as "high ACOS," since
  spend with no return is arguably the worse case.
- The date picker in Tab 2 only lists dates that actually have data for that
  specific campaign, so it never shows an empty table by default.
