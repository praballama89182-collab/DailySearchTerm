"""
Amazon Sponsored Products — Campaign → Search Term Explorer
-----------------------------------------------------------------
Takes a raw Amazon Search Term report and gives you:

  Tab 1: Overview
      Account-level KPIs plus pie/bar breakdowns — match type
      contribution, how many search terms converted vs didn't,
      how much spend is wasted vs productive, and an ACOS
      distribution across converting search terms.

  Tab 2: Campaign → Search Terms
      Each campaign is expandable; opening it shows every search term
      that ran under it (aggregated across the selected date range),
      with ACOS conditionally colored.

  Tab 3: Campaign → Date → Search Terms
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
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Campaign → Search Term Explorer",
    page_icon="🔍",
    layout="wide",
)

# ----------------------------------------------------------------------
# Visual theme
# ----------------------------------------------------------------------

# Green/red stay reserved for the ACOS good/bad highlighting in the drill-down
# tables (a distinct semantic signal). Everything new in this pass — KPI
# cards, pies, bars — uses shades of navy blue per request, dark to light.
NAVY_SHADES = ["#0B1F3F", "#123A66", "#1B4F8C", "#2566A8",
               "#3E82C4", "#6FA8DC", "#A9C9EA", "#D4E4F5"]
GOOD_RED = "#c5221f"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Roboto+Mono:wght@500;700&display=swap');
html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
.stApp { background-color: #F8F9FA; }
h1, h2, h3 { font-family: 'Roboto', sans-serif; font-weight: 500; color: #202124; }
.kpi-card {
    background: #FFFFFF; border-radius: 12px; padding: 14px 16px;
    box-shadow: 0 1px 3px rgba(60,64,67,.15), 0 1px 2px rgba(60,64,67,.10);
    border-top: 4px solid var(--accent, #123A66); height: 100%;
}
.kpi-label { font-size: 11px; color: #5F6368; font-weight: 500; text-transform: uppercase; letter-spacing: .05em; }
.kpi-value { font-family: 'Roboto Mono', monospace; font-size: 22px; font-weight: 700; color: #202124; margin-top: 3px; }
.section-header { display: flex; align-items: center; gap: 8px; margin: 4px 0 12px 0; }
.section-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.section-title { font-size: 16px; font-weight: 600; color: #202124; }
button[data-baseweb="tab"] { font-weight: 600; font-size: 15px; }
[data-baseweb="tab-highlight"] { background-color: #123A66 !important; }
</style>
""", unsafe_allow_html=True)


def kpi_card(label: str, value: str, color: str) -> str:
    return (f'<div class="kpi-card" style="--accent:{color}">'
            f'<div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>')


def section_header(text: str, color: str = NAVY_SHADES[1]):
    st.markdown(
        f'<div class="section-header"><span class="section-dot" style="background:{color}"></span>'
        f'<span class="section-title">{text}</span></div>',
        unsafe_allow_html=True,
    )


def style_fig(fig, height: int = 380):
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Roboto, sans-serif", color="#202124", size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        colorway=NAVY_SHADES,
    )
    fig.update_xaxes(showgrid=False, linecolor="#DADCE0")
    fig.update_yaxes(showgrid=True, gridcolor="#F1F3F4", zerolinecolor="#DADCE0")
    return fig


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
    df["Match Type"] = df["Match Type"].fillna("-").astype(str)
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


def render_term_table(disp: pd.DataFrame, cols: list, threshold_pct: float, height: int = 320,
                       sort_by=None, ascending: bool = False):
    sort_cols = sort_by if sort_by is not None else "Spend"
    styled = (
        disp[cols]
        .sort_values(sort_cols, ascending=ascending)
        .style.map(lambda v: acos_color(v, threshold_pct), subset=["ACOS %"])
        .format(precision=2)
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=height)


def categorize_portfolio(name: str) -> str:
    """
    Buckets an FBA (non-Vizari) portfolio name into one of 4 categories,
    checked in this priority order: CBT > Exclusive > Ageing > FBA (catch-all).
    """
    n = str(name).lower()
    if "cbt" in n:
        return "CBT"
    elif "exclusive" in n:
        return "Exclusive"
    elif "ageing" in n or "aging" in n:
        return "Ageing"
    else:
        return "FBA"


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

raw_scoped = raw_scoped.copy()
raw_scoped["Portfolio Category"] = raw_scoped["Portfolio name"].apply(categorize_portfolio)
category_order = ["CBT", "Exclusive", "Ageing", "FBA"]
selected_categories = st.sidebar.multiselect(
    "Portfolio Category", category_order, default=[],
    help="CBT = portfolio name contains 'CBT'. Exclusive = contains 'Exclusive'. "
         "Ageing = contains 'Ageing'/'Aging'. FBA = everything else (the catch-all bucket). "
         "Checked in that priority order, so a name matching multiple only counts once."
)

match_types = sorted(raw_scoped["Match Type"].dropna().unique())
selected_match_types = st.sidebar.multiselect("Match Type", match_types, default=[])

st.sidebar.markdown("---")
st.sidebar.subheader("Display settings")
acos_threshold = st.sidebar.number_input("ACOS highlight threshold (%)", min_value=0.0, value=5.0, step=1.0,
                                          help="Below this = light green. At/above this (or no sales) = light red.")
sort_campaigns_by = st.sidebar.selectbox("Sort campaigns by", ["Spend", "Sales", "Clicks", "Campaign Name"])
max_campaigns = st.sidebar.slider("Max campaigns to display", min_value=5, max_value=500, value=500, step=5,
                                   help="Every campaign with at least 1 click in the date range qualifies — "
                                        "this only caps how many render at once for page speed. Defaults to "
                                        "500 so it effectively shows all of them; lower it if the page feels slow.")

# ----------------------------------------------------------------------
# Filter (date / portfolio category / match type — campaign name search
# happens further down, in the main area, right above the campaign list)
# ----------------------------------------------------------------------

df = raw_scoped[(raw_scoped["Date"].dt.date >= start_date) & (raw_scoped["Date"].dt.date <= end_date)].copy()
if selected_categories:
    df = df[df["Portfolio Category"].isin(selected_categories)]
if selected_match_types:
    df = df[df["Match Type"].isin(selected_match_types)]

if df.empty:
    st.warning("No rows match the current filters.")
    st.stop()

st.title("Campaign → Search Term Explorer")

st.markdown("###### Campaign name search")
scol1, scol2 = st.columns([3, 1])
with scol1:
    campaign_query = st.text_input("Campaign name", label_visibility="collapsed",
                                    placeholder="Search or filter by campaign name / prefix…")
with scol2:
    match_mode = st.radio("Match mode", ["Contains", "Starts with"], horizontal=True, label_visibility="collapsed")

if campaign_query:
    if match_mode == "Contains":
        df = df[df["Campaign Name"].str.contains(campaign_query, case=False, na=False)]
    else:
        df = df[df["Campaign Name"].str.lower().str.startswith(campaign_query.lower())]

# search terms with zero clicks across the entire current scope are excluded everywhere
_term_clicks = df.groupby("Customer Search Term")["Clicks"].transform("sum")
df = df[_term_clicks > 0]

if df.empty:
    st.warning("No rows match the current filters.")
    st.stop()

scope_label = "FBA portfolios only (excl. Vizari)" if fba_only else "all portfolios"
st.caption(f"{df['Campaign Name'].nunique()} campaigns match · {scope_label} · "
           f"{start_date} → {end_date} · {len(df):,} rows · search terms with zero clicks excluded")

# campaign ranking / limiting — a campaign qualifies once it has at least 1 click
# in the current date range (redundant with the term-level click filter above,
# but made explicit here so campaign inclusion isn't just an incidental side effect)
camp_totals = aggregate(df, ["Campaign Name"])
camp_totals = camp_totals[camp_totals["Clicks"] >= 1]
if sort_campaigns_by == "Campaign Name":
    camp_order = camp_totals.sort_values("Campaign Name")["Campaign Name"].tolist()
else:
    camp_order = camp_totals.sort_values(sort_campaigns_by, ascending=False)["Campaign Name"].tolist()
shown_campaigns = camp_order[:max_campaigns]

camp_groups = df.groupby("Campaign Name")

tab_overview, tab_by_term, tab_by_date, tab_conv_nonconv = st.tabs(
    ["📊 Overview", "📋 Campaign → Search Terms", "📅 Campaign → Date", "🔀 Converting vs Non-Converting"]
)

TERM_COLS = ["Customer Search Term", "Match Type", "Impressions", "Clicks",
             "Spend", "Sales", "Orders", "ACOS %", "ROAS", "CVR %", "CTR %"]
DATE_TERM_COLS = ["Date", "Customer Search Term", "Match Type", "Impressions", "Clicks",
                  "Spend", "Sales", "Orders", "ACOS %", "ROAS", "CVR %", "CTR %"]

# ----------------------------------------------------------------------
# Tab 1: Overview
# ----------------------------------------------------------------------

with tab_overview:
    totals = compute_metrics(pd.DataFrame([{
        "Impressions": df["Impressions"].sum(), "Clicks": df["Clicks"].sum(),
        "Spend": df["Spend"].sum(), "Sales": df["Sales"].sum(), "Orders": df["Orders"].sum(),
    }])).iloc[0]

    kpis = [
        ("Sales", f"${totals['Sales']:,.0f}"),
        ("Spend", f"${totals['Spend']:,.0f}"),
        ("ACOS", f"{totals['ACOS']*100:.1f}%" if pd.notna(totals['ACOS']) else "—"),
        ("CTR", f"{totals['CTR']*100:.2f}%" if pd.notna(totals['CTR']) else "—"),
        ("CVR", f"{totals['CVR']*100:.2f}%" if pd.notna(totals['CVR']) else "—"),
        ("ROAS", f"{totals['ROAS']:.2f}" if pd.notna(totals['ROAS']) else "—"),
    ]
    kpi_cols = st.columns(6)
    for i, (col, (label, value)) in enumerate(zip(kpi_cols, kpis)):
        with col:
            st.markdown(kpi_card(label, value, NAVY_SHADES[i % len(NAVY_SHADES)]), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # search-term-level rollup across the current filters (one row per term)
    term_level = aggregate(df, ["Customer Search Term"])
    no_sales = term_level[term_level["Sales"] == 0]
    with_sales = term_level[term_level["Sales"] > 0]
    spend_no_sales = no_sales["Spend"].sum()
    spend_with_sales = with_sales["Spend"].sum()
    acos_converting = spend_with_sales / with_sales["Sales"].sum() if with_sales["Sales"].sum() > 0 else np.nan

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            section_header("Match Type Contribution", NAVY_SHADES[1])
            match_metric = st.selectbox("Metric", ["Spend share", "Sales share", "Clicks share"], key="mt_metric")
            by_match = aggregate(df, ["Match Type"])
            value_col = {"Spend share": "Spend", "Sales share": "Sales", "Clicks share": "Clicks"}[match_metric]
            fig = px.pie(by_match, names="Match Type", values=value_col, hole=0.45,
                        color_discrete_sequence=NAVY_SHADES)
            fig.update_traces(textinfo="label+percent", textposition="outside")
            style_fig(fig, height=380)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        with st.container(border=True):
            section_header("Search Terms: Converting vs Non-Converting", NAVY_SHADES[2])
            count_df = pd.DataFrame({
                "Group": ["With sales", "No sales"],
                "Count": [len(with_sales), len(no_sales)],
            })
            fig = px.pie(count_df, names="Group", values="Count", hole=0.45,
                        color_discrete_sequence=[NAVY_SHADES[1], NAVY_SHADES[6]])
            fig.update_traces(textinfo="label+percent+value", textposition="outside")
            style_fig(fig, height=380)
            st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            section_header("Spend Share: Productive vs Wasted", NAVY_SHADES[3])
            st.caption("Wasted = spend on search terms with zero sales in the current filters.")
            spend_df = pd.DataFrame({
                "Group": ["Productive (has sales)", "Wasted (no sales)"],
                "Spend": [spend_with_sales, spend_no_sales],
            })
            fig = px.pie(spend_df, names="Group", values="Spend", hole=0.45,
                        color_discrete_sequence=[NAVY_SHADES[1], NAVY_SHADES[6]])
            fig.update_traces(textinfo="label+percent", textposition="outside")
            style_fig(fig, height=380)
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        with st.container(border=True):
            section_header("Converting vs Blended ACOS", NAVY_SHADES[2])
            st.caption("Blended ACOS includes wasted spend from non-converting terms. Converting-only "
                       "ACOS shows what your ACOS would be if every dollar went to terms that sold.")
            comp_df = pd.DataFrame({
                "Metric": ["Blended ACOS (all spend)", "Converting-only ACOS"],
                "ACOS": [totals["ACOS"] if pd.notna(totals["ACOS"]) else 0,
                         acos_converting if pd.notna(acos_converting) else 0],
            })
            fig = px.bar(comp_df, x="Metric", y="ACOS", color="Metric",
                        color_discrete_sequence=[NAVY_SHADES[5], NAVY_SHADES[1]],
                        text=comp_df["ACOS"].apply(lambda v: f"{v*100:.1f}%"))
            fig.update_yaxes(tickformat=".0%")
            fig.update_traces(textposition="outside")
            fig.update_layout(showlegend=False)
            style_fig(fig, height=380)
            st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        section_header("ACOS Distribution — Converting Search Terms", NAVY_SHADES[1])
        st.caption("Where converting search terms fall relative to your ACOS bands — bar height/color "
                   "both scale with the number of search terms in each band.")
        band_metric = st.selectbox("Show", ["Number of search terms", "Spend in band"], key="band_metric")
        bins = [0, 0.05, 0.15, 0.30, 0.50, np.inf]
        labels = ["<5%", "5–15%", "15–30%", "30–50%", ">50%"]
        ws = with_sales.copy()
        ws["ACOS Band"] = pd.cut(ws["ACOS"], bins=bins, labels=labels, right=False)
        band_agg = ws.groupby("ACOS Band", observed=False).agg(
            Count=("Customer Search Term", "count"), Spend=("Spend", "sum")
        ).reindex(labels).fillna(0)
        y_col = "Count" if band_metric == "Number of search terms" else "Spend"
        fig = go.Figure(go.Bar(
            x=band_agg.index, y=band_agg[y_col],
            marker=dict(color=NAVY_SHADES[:len(band_agg)]),
            text=band_agg[y_col].apply(lambda v: f"{v:,.0f}"), textposition="outside",
        ))
        fig.update_layout(xaxis_title="ACOS band", yaxis_title=band_metric)
        style_fig(fig, height=380)
        st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        section_header("Spend Distribution — Non-Converting Search Terms", NAVY_SHADES[4])
        st.caption("Non-converting terms have zero sales, so ACOS is undefined for every one of them "
                   "(spend ÷ $0) — an 'ACOS band' chart would just be one meaningless bucket. Spend "
                   "bands are the useful equivalent here: they show whether wasted spend is concentrated "
                   "in a handful of expensive terms or spread thin across many cheap ones.")
        ns_band_metric = st.selectbox("Show", ["Number of search terms", "Spend in band"], key="ns_band_metric")
        spend_bins = [0, 5, 15, 30, 50, np.inf]
        spend_labels = ["<$5", "$5–15", "$15–30", "$30–50", ">$50"]
        ns = no_sales.copy()
        ns["Spend Band"] = pd.cut(ns["Spend"], bins=spend_bins, labels=spend_labels, right=False)
        ns_band_agg = ns.groupby("Spend Band", observed=False).agg(
            Count=("Customer Search Term", "count"), Spend=("Spend", "sum")
        ).reindex(spend_labels).fillna(0)
        ns_y_col = "Count" if ns_band_metric == "Number of search terms" else "Spend"
        fig = go.Figure(go.Bar(
            x=ns_band_agg.index, y=ns_band_agg[ns_y_col],
            marker=dict(color=NAVY_SHADES[:len(ns_band_agg)]),
            text=ns_band_agg[ns_y_col].apply(lambda v: f"{v:,.0f}"), textposition="outside",
        ))
        fig.update_layout(xaxis_title="Spend band", yaxis_title=ns_band_metric)
        style_fig(fig, height=380)
        st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        section_header("Non-Converting Spend vs Overall Spend", NAVY_SHADES[0])
        pct_wasted = (spend_no_sales / totals["Spend"] * 100) if totals["Spend"] > 0 else 0
        st.caption(f"${spend_no_sales:,.2f} of ${totals['Spend']:,.2f} total spend "
                   f"({pct_wasted:.1f}%) went to search terms that never generated a sale.")
        cmp_df = pd.DataFrame({
            "Group": ["Overall Spend", "Non-Converting Spend"],
            "Spend": [totals["Spend"], spend_no_sales],
        })
        fig = go.Figure(go.Bar(
            x=cmp_df["Group"], y=cmp_df["Spend"],
            marker=dict(color=[NAVY_SHADES[1], NAVY_SHADES[5]]),
            text=[f"${v:,.0f}" for v in cmp_df["Spend"]], textposition="outside",
        ))
        fig.add_annotation(
            x="Non-Converting Spend", y=spend_no_sales, text=f"{pct_wasted:.1f}% of total",
            showarrow=False, yshift=28, font=dict(size=13, color=NAVY_SHADES[0]),
        )
        fig.update_layout(yaxis_title="Spend ($)")
        style_fig(fig, height=380)
        st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# Tab 2: Campaign → Search Terms
# ----------------------------------------------------------------------

with tab_by_term:
    if len(camp_order) > max_campaigns:
        st.info(f"Showing the top {max_campaigns} of {len(camp_order)} matching campaigns "
                 f"(sorted by {sort_campaigns_by}). Narrow the campaign search or raise the limit in the sidebar to see more.")
    st.caption(f"ACOS below {acos_threshold:.0f}% is highlighted light green; at/above (or no sales) is light red.")
    for camp in shown_campaigns:
        g = camp_groups.get_group(camp)
        totals = aggregate(g, ["Campaign Name"]).iloc[0]
        label = (f"{camp}  ·  ${totals['Spend']:,.0f} spend  ·  "
                 f"{totals['ACOS']*100:.1f}% ACOS" if pd.notna(totals['ACOS']) else
                 f"{camp}  ·  ${totals['Spend']:,.0f} spend  ·  no sales")
        with st.expander(label):
            st.code(camp, language=None)
            kpi_cols = st.columns(4)
            kpis = [
                ("Spend", f"${totals['Spend']:,.0f}", NAVY_SHADES[0]),
                ("Sales", f"${totals['Sales']:,.0f}", NAVY_SHADES[2]),
                ("ACOS", f"{totals['ACOS']*100:.1f}%" if pd.notna(totals['ACOS']) else "—", NAVY_SHADES[4]),
                ("ROAS", f"{totals['ROAS']:.2f}" if pd.notna(totals['ROAS']) else "—", NAVY_SHADES[1]),
            ]
            for col, (lbl, val, color) in zip(kpi_cols, kpis):
                with col:
                    st.markdown(kpi_card(lbl, val, color), unsafe_allow_html=True)

            term_agg = aggregate(g, ["Customer Search Term", "Match Type"])
            disp = format_term_table(term_agg)
            st.markdown(f"**{len(disp)} search term(s)**")
            render_term_table(disp, TERM_COLS, acos_threshold)

# ----------------------------------------------------------------------
# Tab 3: Campaign → Date → Search Terms
# ----------------------------------------------------------------------

with tab_by_date:
    if len(camp_order) > max_campaigns:
        st.info(f"Showing the top {max_campaigns} of {len(camp_order)} matching campaigns "
                 f"(sorted by {sort_campaigns_by}). Narrow the campaign search or raise the limit in the sidebar to see more.")
    st.caption(f"Expand a campaign to see every date and every search term under it in one scrollable "
               f"table, most recent date first. ACOS below {acos_threshold:.0f}% is light green; "
               f"at/above (or no sales) is light red.")
    for camp in shown_campaigns:
        g = camp_groups.get_group(camp)
        totals = aggregate(g, ["Campaign Name"]).iloc[0]
        label = (f"{camp}  ·  ${totals['Spend']:,.0f} spend  ·  "
                 f"{totals['ACOS']*100:.1f}% ACOS" if pd.notna(totals['ACOS']) else
                 f"{camp}  ·  ${totals['Spend']:,.0f} spend  ·  no sales")
        with st.expander(label):
            st.code(camp, language=None)
            kpi_cols = st.columns(4)
            kpis = [
                ("Spend", f"${totals['Spend']:,.0f}", NAVY_SHADES[0]),
                ("Sales", f"${totals['Sales']:,.0f}", NAVY_SHADES[2]),
                ("ACOS", f"{totals['ACOS']*100:.1f}%" if pd.notna(totals['ACOS']) else "—", NAVY_SHADES[4]),
                ("ROAS", f"{totals['ROAS']:.2f}" if pd.notna(totals['ROAS']) else "—", NAVY_SHADES[1]),
            ]
            for col, (lbl, val, color) in zip(kpi_cols, kpis):
                with col:
                    st.markdown(kpi_card(lbl, val, color), unsafe_allow_html=True)

            date_term_agg = aggregate(g, ["Date", "Customer Search Term", "Match Type"])
            disp = format_term_table(date_term_agg)
            disp["Date"] = disp["Date"].dt.strftime("%Y-%m-%d")
            st.markdown(f"**{len(disp)} date × search-term row(s)**")
            render_term_table(disp, DATE_TERM_COLS, acos_threshold, height=500,
                               sort_by=["Date", "Spend"], ascending=[False, False])

# ----------------------------------------------------------------------
# Tab 4: Converting vs Non-Converting
# ----------------------------------------------------------------------

with tab_conv_nonconv:
    st.caption("Pick a view, then expand a campaign to see just its converting or just its "
               f"non-converting search terms. ACOS below {acos_threshold:.0f}% is light green; "
               "at/above (or no sales) is light red.")

    fcol1, fcol2 = st.columns([1, 1])
    with fcol1:
        view_choice = st.radio("View", ["Non-Converting", "Converting"], horizontal=True, key="conv_view")
    with fcol2:
        min_clicks_nonconv = 0
        if view_choice == "Non-Converting":
            min_clicks_nonconv = st.number_input(
                "Min clicks (non-converting terms only)", min_value=0, value=1, step=1, key="min_clicks_nonconv",
                help="Filters out negligible non-converting terms — e.g. a single stray click with no "
                     "sale is less actionable than a term with 20 clicks and still no sale."
            )

    shown_any = False
    for camp in shown_campaigns:
        g = camp_groups.get_group(camp)
        term_agg = aggregate(g, ["Customer Search Term", "Match Type"])

        if view_choice == "Converting":
            sub = term_agg[term_agg["Sales"] > 0]
        else:
            sub = term_agg[(term_agg["Sales"] == 0) & (term_agg["Clicks"] >= min_clicks_nonconv)]

        if sub.empty:
            continue
        shown_any = True

        sub_totals = compute_metrics(pd.DataFrame([{
            "Impressions": sub["Impressions"].sum(), "Clicks": sub["Clicks"].sum(),
            "Spend": sub["Spend"].sum(), "Sales": sub["Sales"].sum(), "Orders": sub["Orders"].sum(),
        }])).iloc[0]

        label = (f"{camp}  ·  {len(sub)} {view_choice.lower()} term(s)  ·  ${sub_totals['Spend']:,.0f} spend")
        with st.expander(label):
            st.code(camp, language=None)
            kpi_cols = st.columns(4)
            kpis = [
                ("Spend", f"${sub_totals['Spend']:,.0f}", NAVY_SHADES[0]),
                ("Sales", f"${sub_totals['Sales']:,.0f}", NAVY_SHADES[2]),
                ("ACOS", f"{sub_totals['ACOS']*100:.1f}%" if pd.notna(sub_totals['ACOS']) else "—", NAVY_SHADES[4]),
                ("ROAS", f"{sub_totals['ROAS']:.2f}" if pd.notna(sub_totals['ROAS']) else "—", NAVY_SHADES[1]),
            ]
            for col, (lbl, val, color) in zip(kpi_cols, kpis):
                with col:
                    st.markdown(kpi_card(lbl, val, color), unsafe_allow_html=True)

            disp = format_term_table(sub)
            st.markdown(f"**{len(disp)} {view_choice.lower()} search term(s)**")
            render_term_table(disp, TERM_COLS, acos_threshold)

    if not shown_any:
        st.info(f"No campaigns have {view_choice.lower()} search terms matching the current filters"
                + (f" and the {min_clicks_nonconv}-click minimum." if view_choice == "Non-Converting" else "."))
