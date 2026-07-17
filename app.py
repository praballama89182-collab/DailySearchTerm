"""
Amazon Sponsored Products — Campaign → Search Term Explorer
-----------------------------------------------------------------
Takes a raw Amazon Search Term report and lets you drill down:

  Tab 1: Campaign → Search Terms
      Each campaign is expandable; opening it shows every search term
      that ran under it (aggregated across the selected date range),
      with ACOS conditionally colored.

  Tab 2: Campaign → Date → Search Terms
      Each campaign is expandable; opening it shows a date picker, and
      selecting a date shows every search term's performance on that
      single day, with ACOS conditionally colored.

Scope: only portfolios whose name contains "FBA" are considered,
EXCLUDING any portfolio that also contains "Vizari".

Run locally:
    pip install -r requirements.txt
    streamlit run app.py
"""

import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(
    page_title="Campaign → Search Term Explorer",
    page_icon="🔍",
    layout="wide",
)

# ----------------------------------------------------------------------
# Visual theme — consistent with the rest of the tool suite
# ----------------------------------------------------------------------

PALETTE = {
    "blue": "#4285F4", "red": "#EA4335", "yellow": "#FBBC04",
    "green": "#34A853", "purple": "#A142F4", "teal": "#24C1E0",
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Roboto+Mono:wght@500;700&display=swap');
html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
.stApp { background-color: #F8F9FA; }
h1, h2, h3 { font-family: 'Roboto', sans-serif; font-weight: 500; color: #202124; }
.kpi-card {
    background: #FFFFFF; border-radius: 12px; padding: 14px 16px;
    box-shadow: 0 1px 3px rgba(60,64,67,.15), 0 1px 2px rgba(60,64,67,.10);
    border-top: 4px solid var(--accent, #4285F4); height: 100%;
}
.kpi-label { font-size: 11px; color: #5F6368; font-weight: 500; text-transform: uppercase; letter-spacing: .05em; }
.kpi-value { font-family: 'Roboto Mono', monospace; font-size: 22px; font-weight: 700; color: #202124; margin-top: 3px; }
button[data-baseweb="tab"] { font-weight: 600; font-size: 15px; }
[data-baseweb="tab-highlight"] { background-color: #4285F4 !important; }
</style>
""", unsafe_allow_html=True)


def kpi_card(label: str, value: str, color: str) -> str:
    return (f'<div class="kpi-card" style="--accent:{color}">'
            f'<div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>')


# ----------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------

RENAME_MAP = {
    "7 Day Total Sales": "Sales",
    "Total Advertising Cost of Sales (ACOS)": "ACOS_reported",
    "Total Return on Advertising Spend (ROAS)": "ROAS_reported",
    "7 Day Total Orders (#)": "Orders",
    "7 Day Total Units (#)": "Units",
    "Cost Per Click (CPC)": "CPC_reported",
    "Click-Thru Rate (CTR)": "CTR_reported",
    "7 Day Conversion Rate": "CVR_reported",
}

REQUIRED_COLS = [
    "Date", "Portfolio name", "Campaign Name", "Customer Search Term",
    "Match Type", "Impressions", "Clicks", "Spend", "Sales", "Orders",
]


@st.cache_data(show_spinner="Reading report…")
def load_report(file) -> pd.DataFrame:
    df = pd.read_excel(file, sheet_name=0)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns=RENAME_MAP)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Report is missing expected columns: {missing}")

    df["Date"] = pd.to_datetime(df["Date"])
    df["Portfolio name"] = df["Portfolio name"].fillna("No Portfolio")
    df["Customer Search Term"] = df["Customer Search Term"].fillna("").astype(str)
    for col in ["Impressions", "Clicks", "Spend", "Sales", "Orders"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Always recomputed from summed Spend/Sales/Clicks/Impressions — never
    averaged from the report's own per-row ratio columns, which go blank on
    zero-click/zero-sale rows and can't be validly averaged."""
    out = df.copy()
    out["CTR"] = np.where(out["Impressions"] > 0, out["Clicks"] / out["Impressions"], np.nan)
    out["CVR"] = np.where(out["Clicks"] > 0, out["Orders"] / out["Clicks"], np.nan)
    out["CPC"] = np.where(out["Clicks"] > 0, out["Spend"] / out["Clicks"], np.nan)
    out["ACOS"] = np.where(out["Sales"] > 0, out["Spend"] / out["Sales"], np.nan)
    out["ROAS"] = np.where(out["Spend"] > 0, out["Sales"] / out["Spend"], np.nan)
    return out


def aggregate(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    agg = (
        df.groupby(group_cols, as_index=False)
        .agg(Impressions=("Impressions", "sum"), Clicks=("Clicks", "sum"),
             Spend=("Spend", "sum"), Sales=("Sales", "sum"), Orders=("Orders", "sum"))
    )
    return compute_metrics(agg)


def format_term_table(agg_df: pd.DataFrame) -> pd.DataFrame:
    disp = agg_df.copy()
    disp["ACOS %"] = (disp["ACOS"] * 100).round(1)
    disp["ROAS"] = disp["ROAS"].round(2)
    disp["CTR %"] = (disp["CTR"] * 100).round(2)
    disp["CVR %"] = (disp["CVR"] * 100).round(2)
    disp["Spend"] = disp["Spend"].round(2)
    disp["Sales"] = disp["Sales"].round(2)
    return disp


def acos_color(val, threshold_pct):
    if pd.isna(val):
        return "background-color:#fce8e6; color:#c5221f;"  # no sales at all — treat as red
    elif val < threshold_pct:
        return "background-color:#e6f4ea; color:#137333;"
    else:
        return "background-color:#fce8e6; color:#c5221f;"


def render_term_table(disp: pd.DataFrame, cols: list, threshold_pct: float, height: int = 320):
    styled = (
        disp[cols]
        .sort_values("Spend", ascending=False)
        .style.map(lambda v: acos_color(v, threshold_pct), subset=["ACOS %"])
        .format(precision=2)
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=height)


# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------

st.sidebar.title("🔍 Search Term Explorer")
uploaded = st.sidebar.file_uploader("Upload raw Search Term report (.xlsx)", type=["xlsx"])

if uploaded is None:
    st.title("Campaign → Search Term Explorer")
    st.info("👈 Upload a raw Amazon Sponsored Products Search Term report (.xlsx) to begin. "
            "Expected columns include Date, Portfolio name, Campaign Name, Customer Search Term, "
            "Match Type, Impressions, Clicks, Spend, 7 Day Total Sales, 7 Day Total Orders.")
    st.stop()

try:
    raw = load_report(uploaded)
except Exception as e:
    st.error(f"Couldn't read this file: {e}")
    st.stop()

st.sidebar.markdown("---")
fba_only = st.sidebar.checkbox(
    "Only FBA portfolios (excludes Vizari)", value=True,
    help="Keeps any portfolio whose name contains 'FBA', but always excludes portfolios "
         "containing 'Vizari' even if they also happen to contain 'FBA'."
)
is_fba = raw["Portfolio name"].str.contains("FBA", case=False, na=False)
is_vizari = raw["Portfolio name"].str.contains("Vizari", case=False, na=False)
scope_mask = (is_fba & ~is_vizari) if fba_only else pd.Series(True, index=raw.index)
raw_scoped = raw[scope_mask]

if fba_only:
    st.sidebar.caption(f"Scoped to {raw_scoped['Portfolio name'].nunique()} FBA portfolios, "
                        f"{raw_scoped['Campaign Name'].nunique()} campaigns.")

if raw_scoped.empty:
    st.error("No rows match an 'FBA' portfolio name (excluding Vizari) in this file. "
              "Uncheck the filter to see all data.")
    st.stop()

min_date, max_date = raw_scoped["Date"].min().date(), raw_scoped["Date"].max().date()
date_range = st.sidebar.date_input("Date range", (min_date, max_date), min_value=min_date, max_value=max_date)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

portfolios = sorted(raw_scoped["Portfolio name"].dropna().unique())
selected_portfolios = st.sidebar.multiselect("Portfolio", portfolios, default=[])

st.sidebar.markdown("---")
st.sidebar.subheader("Campaign search")
campaign_query = st.sidebar.text_input("Campaign name")
match_mode = st.sidebar.radio("Match mode", ["Contains", "Starts with"], horizontal=True)

st.sidebar.markdown("---")
st.sidebar.subheader("Display settings")
acos_threshold = st.sidebar.number_input("ACOS highlight threshold (%)", min_value=0.0, value=5.0, step=1.0,
                                          help="Below this = light green. At/above this (or no sales) = light red.")
sort_campaigns_by = st.sidebar.selectbox("Sort campaigns by", ["Spend", "Sales", "Clicks", "Campaign Name"])
max_campaigns = st.sidebar.slider("Max campaigns to display", min_value=5, max_value=200, value=30, step=5,
                                   help="Keeps the page responsive — narrow with the search box above to see more.")

# ----------------------------------------------------------------------
# Filter
# ----------------------------------------------------------------------

df = raw_scoped[(raw_scoped["Date"].dt.date >= start_date) & (raw_scoped["Date"].dt.date <= end_date)].copy()
if selected_portfolios:
    df = df[df["Portfolio name"].isin(selected_portfolios)]
if campaign_query:
    if match_mode == "Contains":
        df = df[df["Campaign Name"].str.contains(campaign_query, case=False, na=False)]
    else:
        df = df[df["Campaign Name"].str.lower().str.startswith(campaign_query.lower())]

if df.empty:
    st.warning("No rows match the current filters.")
    st.stop()

st.title("Campaign → Search Term Explorer")
scope_label = "FBA portfolios only (excl. Vizari)" if fba_only else "all portfolios"
st.caption(f"{df['Campaign Name'].nunique()} campaigns match · {scope_label} · "
           f"{start_date} → {end_date} · {len(df):,} rows")

# campaign ranking / limiting
camp_totals = aggregate(df, ["Campaign Name"])
if sort_campaigns_by == "Campaign Name":
    camp_order = camp_totals.sort_values("Campaign Name")["Campaign Name"].tolist()
else:
    camp_order = camp_totals.sort_values(sort_campaigns_by, ascending=False)["Campaign Name"].tolist()
shown_campaigns = camp_order[:max_campaigns]

if len(camp_order) > max_campaigns:
    st.info(f"Showing the top {max_campaigns} of {len(camp_order)} matching campaigns "
             f"(sorted by {sort_campaigns_by}). Narrow the campaign search or raise the limit in the sidebar to see more.")

camp_groups = df.groupby("Campaign Name")

tab_by_term, tab_by_date = st.tabs(["📋 Campaign → Search Terms", "📅 Campaign → Date → Search Terms"])

TERM_COLS = ["Customer Search Term", "Match Type", "Impressions", "Clicks",
             "Spend", "Sales", "Orders", "ACOS %", "ROAS", "CVR %", "CTR %"]

# ----------------------------------------------------------------------
# Tab 1: Campaign → Search Terms
# ----------------------------------------------------------------------

with tab_by_term:
    st.caption(f"ACOS below {acos_threshold:.0f}% is highlighted light green; at/above (or no sales) is light red.")
    for camp in shown_campaigns:
        g = camp_groups.get_group(camp)
        totals = aggregate(g, ["Campaign Name"]).iloc[0]
        label = (f"{camp}  ·  ${totals['Spend']:,.0f} spend  ·  "
                 f"{totals['ACOS']*100:.1f}% ACOS" if pd.notna(totals['ACOS']) else
                 f"{camp}  ·  ${totals['Spend']:,.0f} spend  ·  no sales")
        with st.expander(label):
            kpi_cols = st.columns(4)
            kpis = [
                ("Spend", f"${totals['Spend']:,.0f}", PALETTE["red"]),
                ("Sales", f"${totals['Sales']:,.0f}", PALETTE["green"]),
                ("ACOS", f"{totals['ACOS']*100:.1f}%" if pd.notna(totals['ACOS']) else "—", PALETTE["yellow"]),
                ("ROAS", f"{totals['ROAS']:.2f}" if pd.notna(totals['ROAS']) else "—", PALETTE["purple"]),
            ]
            for col, (lbl, val, color) in zip(kpi_cols, kpis):
                with col:
                    st.markdown(kpi_card(lbl, val, color), unsafe_allow_html=True)

            term_agg = aggregate(g, ["Customer Search Term", "Match Type"])
            disp = format_term_table(term_agg)
            st.markdown(f"**{len(disp)} search term(s)**")
            render_term_table(disp, TERM_COLS, acos_threshold)

# ----------------------------------------------------------------------
# Tab 2: Campaign → Date → Search Terms
# ----------------------------------------------------------------------

with tab_by_date:
    st.caption(f"Expand a campaign, then pick a date to see that day's search term performance. "
               f"ACOS below {acos_threshold:.0f}% is light green; at/above (or no sales) is light red.")
    for camp in shown_campaigns:
        g = camp_groups.get_group(camp)
        totals = aggregate(g, ["Campaign Name"]).iloc[0]
        label = f"{camp}  ·  ${totals['Spend']:,.0f} spend"
        with st.expander(label):
            available_dates = sorted(g["Date"].dt.date.unique(), reverse=True)
            selected_date = st.selectbox(
                "Date", available_dates, key=f"date_{camp}",
                format_func=lambda d: d.strftime("%Y-%m-%d"),
            )
            day_df = g[g["Date"].dt.date == selected_date]
            day_totals = aggregate(day_df, ["Campaign Name"]).iloc[0]

            kpi_cols = st.columns(4)
            kpis = [
                ("Spend", f"${day_totals['Spend']:,.0f}", PALETTE["red"]),
                ("Sales", f"${day_totals['Sales']:,.0f}", PALETTE["green"]),
                ("ACOS", f"{day_totals['ACOS']*100:.1f}%" if pd.notna(day_totals['ACOS']) else "—", PALETTE["yellow"]),
                ("ROAS", f"{day_totals['ROAS']:.2f}" if pd.notna(day_totals['ROAS']) else "—", PALETTE["purple"]),
            ]
            for col, (lbl, val, color) in zip(kpi_cols, kpis):
                with col:
                    st.markdown(kpi_card(lbl, val, color), unsafe_allow_html=True)

            term_agg = aggregate(day_df, ["Customer Search Term", "Match Type"])
            disp = format_term_table(term_agg)
            st.markdown(f"**{len(disp)} search term(s) on {selected_date}**")
            render_term_table(disp, TERM_COLS, acos_threshold)
