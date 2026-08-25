"""
CHPP-PIS — 04_Production_Analytics.py
Production Analytics module.

Purpose:
- Analyse actual production records already stored in Supabase.
- Provide Day / Month / Year reporting.
- Highlight Peas and Nuts as key clean-coal streams.
- Calculate production totals, recovery, reject ratio and capacity performance
  only from fields that actually exist in the database.
- Do not invent quality data or missing production values.

Expected Supabase table:
    public.chpp_production_kpis

The code is deliberately defensive because the production table may evolve.
It detects common column-name variations and displays "Not available" when a
required field is genuinely absent.
"""

from __future__ import annotations

from auth import require_login, show_user_sidebar

# ============================================================
# AUTHENTICATION
# ============================================================

user = require_login(
    allowed_roles=[
        "Administrator",
        "Management",
        "Supervisor",
        "Viewer",
    ]
)

show_user_sidebar()

import os
from pathlib import Path
from datetime import date, datetime
from typing import Any, Optional

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

import pandas as pd
import streamlit as st

try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = Any


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="CHPP-PIS | Production Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

TABLE_NAME = "chpp_production_kpis"
DESIGN_THROUGHPUT_TPH = 200.0
REFERENCE_RECOVERY = 66.7

FIELD_ALIASES = {
    "production_date": [
        "production_date",
        "date",
        "prod_date",
        "production_day",
    ],
    "dmc_feed_tons": [
        "dmc_feed_tons",
        "dmc_feed",
        "feed_tons",
        "dmc_feed_tonnes",
    ],
    "clean_coal_tons": [
        "clean_coal_tons",
        "clean_coal",
        "clean_coal_production",
        "product_tons",
        "clean_coal_tonnes",
    ],
    "peas_tons": [
        "peas_tons",
        "peas",
        "peas_production",
        "peas_tonnes",
    ],
    "nuts_tons": [
        "nuts_tons",
        "nuts",
        "nuts_production",
        "nuts_tonnes",
    ],
    "rejects_tons": [
        "rejects_tons",
        "rejects",
        "reject_tons",
        "rejects_tonnes",
    ],
    "fines_tons": [
        "fines_tons",
        "fines",
        "fines_belt_tons",
        "fines_belt",
        "ultrafines_tons",
        "ultrafines",
        "ultrafines_tonnes",
    ],
    "feeder_tons": [
        "feeder_tons",
        "feeder_production_tons",
        "feeder_tonnes",
    ],
    "dmc_running_hours": [
        "dmc_running_hours",
        "dmc_run_hours",
        "dmc_hours",
    ],
    "feeder_running_hours": [
        "feeder_running_hours",
        "feeder_run_hours",
        "feeder_hours",
    ],
    "dmc_availability": [
        "dmc_availability",
        "availability_dmc",
    ],
    "feeder_availability": [
        "feeder_availability",
        "availability_feeder",
    ],
    "dmc_utilization": [
        "dmc_utilization",
        "dmc_utilisation",
    ],
    "feeder_utilization": [
        "feeder_utilization",
        "feeder_utilisation",
    ],
    "dmc_oee": [
        "dmc_oee",
        "oee_dmc",
    ],
    "feeder_oee": [
        "feeder_oee",
        "oee_feeder",
    ],
}


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
<style>
    .main-title {
        font-size: 42px;
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 4px;
    }

    .subtitle {
        color: #9aa4b2;
        font-size: 15px;
        margin-bottom: 20px;
    }

    .section-title {
        color: #5ea1ff;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 2px;
        margin-top: 28px;
        margin-bottom: 12px;
    }

    .status {
        display: inline-block;
        border: 1px solid #16854e;
        color: #35df83;
        border-radius: 22px;
        padding: 8px 15px;
        font-weight: 700;
        font-size: 13px;
    }

    .metric-card {
        background: #111923;
        border: 1px solid #263548;
        border-radius: 12px;
        padding: 18px;
        min-height: 125px;
    }

    .metric-label {
        color: #8da6c4;
        font-size: 13px;
        margin-bottom: 8px;
    }

    .metric-value {
        color: #f4f7fb;
        font-size: 28px;
        font-weight: 700;
    }

    .metric-note {
        color: #7f91a8;
        font-size: 12px;
        margin-top: 8px;
    }

    .insight {
        background: #17210d;
        border-left: 4px solid #a4bd36;
        padding: 14px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
        color: #e8edcf;
    }

    .info-box {
        background: #112238;
        border-left: 4px solid #4d9cff;
        padding: 13px 16px;
        border-radius: 6px;
        color: #cfe2fb;
        margin: 10px 0;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def get_supabase() -> Optional[Client]:
    """Create a Supabase client from Streamlit secrets or the project's .env."""
    if create_client is None:
        return None

    # Explicitly load the CHPP-PIS .env file. This makes the page independent
    # of the directory from which Streamlit was launched.
    if load_dotenv is not None:
        try:
            project_root = Path(__file__).resolve().parent.parent
            env_file = project_root / ".env"
            if env_file.exists():
                load_dotenv(dotenv_path=env_file, override=False)
        except Exception:
            pass

    url = None
    key = None

    # Streamlit secrets first.
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except Exception:
        pass

    # Environment variables / loaded .env second.
    url = url or os.getenv("SUPABASE_URL")
    key = key or os.getenv("SUPABASE_KEY")

    if not url or not key:
        return None

    try:
        return create_client(url, key)
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def load_production_data() -> tuple[pd.DataFrame, Optional[str]]:
    """Load all production KPI records."""
    client = get_supabase()

    if client is None:
        return pd.DataFrame(), "Supabase environment variables are not available."

    try:
        response = client.table(TABLE_NAME).select("*").order(
            "production_date", desc=False
        ).execute()

        rows = response.data or []
        if not rows:
            return pd.DataFrame(), None

        return pd.DataFrame(rows), None

    except Exception as exc:
        return pd.DataFrame(), str(exc)


def find_column(df: pd.DataFrame, aliases: list[str]) -> Optional[str]:
    """Find a real dataframe column from a list of accepted aliases."""
    if df.empty:
        return None

    exact = {str(c).lower(): c for c in df.columns}

    for alias in aliases:
        if alias.lower() in exact:
            return exact[alias.lower()]

    # Normalised comparison for spaces, hyphens and case.
    def norm(value: str) -> str:
        return (
            str(value)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

    normalised = {norm(c): c for c in df.columns}

    for alias in aliases:
        if norm(alias) in normalised:
            return normalised[norm(alias)]

    return None


def build_field_map(df: pd.DataFrame) -> dict[str, Optional[str]]:
    return {
        key: find_column(df, aliases)
        for key, aliases in FIELD_ALIASES.items()
    }


def numeric_series(
    df: pd.DataFrame,
    field_map: dict[str, Optional[str]],
    key: str,
) -> pd.Series:
    col = field_map.get(key)
    if not col or col not in df.columns:
        return pd.Series(index=df.index, dtype="float64")

    return pd.to_numeric(df[col], errors="coerce")


def percentage_value(value: Any) -> Optional[float]:
    """Return a percentage value in 0–100 scale."""
    if value is None:
        return None

    try:
        value = float(value)
    except Exception:
        return None

    # Database values may be stored either as 0.75 or 75.
    if 0 <= value <= 1:
        return value * 100.0

    return value


def aggregate_sum(
    df: pd.DataFrame,
    field_map: dict[str, Optional[str]],
    key: str,
) -> Optional[float]:
    series = numeric_series(df, field_map, key).dropna()
    if series.empty:
        return None
    return float(series.sum())


def latest_or_mean_percentage(
    df: pd.DataFrame,
    field_map: dict[str, Optional[str]],
    key: str,
) -> Optional[float]:
    series = numeric_series(df, field_map, key).dropna()
    if series.empty:
        return None
    return percentage_value(series.mean())


def fmt_tons(value: Optional[float]) -> str:
    if value is None:
        return "Not available"
    return f"{value:,.1f} t"


def fmt_tph(value: Optional[float]) -> str:
    if value is None:
        return "Not available"
    return f"{value:,.1f} tph"


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "Not available"
    return f"{value:,.1f}%"


def fmt_hours(value: Optional[float]) -> str:
    if value is None:
        return "Not available"
    return f"{value:,.2f} h"


def prepare_dates(
    df: pd.DataFrame,
    field_map: dict[str, Optional[str]],
) -> pd.DataFrame:
    """Add a clean internal _production_date column."""
    result = df.copy()
    col = field_map.get("production_date")

    if col and col in result.columns:
        result["_production_date"] = pd.to_datetime(
            result[col], errors="coerce"
        ).dt.normalize()
    else:
        result["_production_date"] = pd.NaT

    return result


def select_period(
    df: pd.DataFrame,
    view: str,
) -> tuple[pd.DataFrame, str]:
    """Return filtered records and a human-readable period description."""
    dates = df["_production_date"].dropna()

    if dates.empty:
        return df.iloc[0:0].copy(), "No production date available"

    min_date = dates.min().date()
    max_date = dates.max().date()

    if view == "Day":
        # Use a real calendar date picker, consistent with the other CHPP-PIS
        # modules. The selectable range is limited to dates represented in
        # the production database, so users cannot accidentally request a
        # date outside the available production history.
        available_dates = sorted(
            dates.dt.date.unique()
        )

        min_date = available_dates[0]
        max_date = available_dates[-1]

        selected = st.date_input(
            "Production Date",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",
        )

        filtered = df[
            df["_production_date"].dt.date == selected
        ].copy()

        return filtered, selected.strftime("%d %b %Y")

    if view == "Month":
        month_values = sorted(
            dates.dt.to_period("M").unique(),
            reverse=True,
        )

        selected = st.selectbox(
            "Production Month",
            month_values,
            format_func=lambda x: x.strftime("%B %Y"),
        )

        filtered = df[
            df["_production_date"].dt.to_period("M") == selected
        ].copy()

        return filtered, selected.strftime("%B %Y")

    year_values = sorted(
        dates.dt.year.dropna().unique(),
        reverse=True,
    )

    selected_year = st.selectbox(
        "Production Year",
        year_values,
    )

    filtered = df[df["_production_date"].dt.year == selected_year].copy()

    return filtered, str(int(selected_year))


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def add_daily_aggregation(
    df: pd.DataFrame,
    field_map: dict[str, Optional[str]],
    keys: list[str],
) -> pd.DataFrame:
    """Aggregate production data by date using only available fields."""
    rows = []

    for production_date, group in df.groupby("_production_date"):
        row = {"Production Date": production_date}

        for key in keys:
            value = aggregate_sum(group, field_map, key)
            row[key] = value

        rows.append(row)

    return pd.DataFrame(rows).sort_values("Production Date")


# ============================================================
# SIDEBAR
# ============================================================

# Authentication/user information is rendered by show_user_sidebar().
# No second local login/sidebar is created here.

# ============================================================
# HEADER
# ============================================================

top_left, top_right = st.columns([5, 1])

with top_left:
    st.markdown(
        '<div class="main-title">📈 CHPP Production Analytics</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="subtitle">'
        "Production trends • clean-coal streams • recovery • capacity performance"
        "</div>",
        unsafe_allow_html=True,
    )

with top_right:
    st.markdown(
        '<div style="text-align:right;margin-top:8px;">'
        '<span class="status">● SYSTEM ONLINE</span>'
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# LOAD DATA
# ============================================================

df, load_error = load_production_data()

if load_error:
    st.error(f"Unable to load production data from Supabase: {load_error}")
    st.stop()

if df.empty:
    st.warning(
        f"No production records were returned from "
        f"`{TABLE_NAME}`."
    )
    st.info(
        "Enter at least one production record in Production Input before "
        "using Production Analytics."
    )
    st.stop()

field_map = build_field_map(df)
df = prepare_dates(df, field_map)

if df["_production_date"].notna().sum() == 0:
    st.error(
        "The production table does not contain a usable production date "
        "field."
    )
    st.stop()


# ============================================================
# REPORTING PERIOD
# ============================================================

st.markdown(
    '<div class="section-title">REPORTING PERIOD</div>',
    unsafe_allow_html=True,
)

view = st.radio(
    "View",
    ["Day", "Month", "Year"],
    horizontal=True,
    label_visibility="visible",
)

period_df, period_label = select_period(df, view)

st.caption(
    f"Showing production analytics for **{period_label}** "
    f"({len(period_df):,} production record(s))."
)

if st.button("↻ Refresh Data", use_container_width=False):
    st.cache_data.clear()
    st.rerun()


if period_df.empty:
    st.warning("No production records exist for the selected period.")
    st.stop()


# ============================================================
# CALCULATIONS
# ============================================================

dmc_feed = aggregate_sum(period_df, field_map, "dmc_feed_tons")
clean_coal = aggregate_sum(period_df, field_map, "clean_coal_tons")
peas = aggregate_sum(period_df, field_map, "peas_tons")
nuts = aggregate_sum(period_df, field_map, "nuts_tons")
rejects = aggregate_sum(period_df, field_map, "rejects_tons")
fines = aggregate_sum(period_df, field_map, "fines_tons")

# If clean coal is not explicitly stored but Peas and Nuts are present,
# derive clean coal strictly from those actual streams.
if clean_coal is None and peas is not None and nuts is not None:
    clean_coal = peas + nuts

# If feed is absent but clean coal/rejects/fines exist, derive it only as
# an explicitly labelled material-balance estimate.
derived_feed = False
if dmc_feed is None:
    components = [x for x in [clean_coal, rejects, fines] if x is not None]
    if components:
        dmc_feed = sum(components)
        derived_feed = True

recovery = None
reject_ratio = None
peas_share = None
nuts_share = None
clean_coal_share = None

if dmc_feed is not None and dmc_feed > 0:
    if clean_coal is not None:
        recovery = clean_coal / dmc_feed * 100.0

    if rejects is not None:
        reject_ratio = rejects / dmc_feed * 100.0

if clean_coal is not None and clean_coal > 0:
    if peas is not None:
        peas_share = peas / clean_coal * 100.0
    if nuts is not None:
        nuts_share = nuts / clean_coal * 100.0

if dmc_feed is not None and dmc_feed > 0:
    clean_coal_share = (
        clean_coal / dmc_feed * 100.0
        if clean_coal is not None
        else None
    )

dmc_running_hours = aggregate_sum(
    period_df, field_map, "dmc_running_hours"
)
feeder_running_hours = aggregate_sum(
    period_df, field_map, "feeder_running_hours"
)

dmc_availability = latest_or_mean_percentage(
    period_df, field_map, "dmc_availability"
)
feeder_availability = latest_or_mean_percentage(
    period_df, field_map, "feeder_availability"
)
dmc_utilization = latest_or_mean_percentage(
    period_df, field_map, "dmc_utilization"
)
feeder_utilization = latest_or_mean_percentage(
    period_df, field_map, "feeder_utilization"
)
dmc_oee = latest_or_mean_percentage(period_df, field_map, "dmc_oee")
feeder_oee = latest_or_mean_percentage(period_df, field_map, "feeder_oee")

dmc_throughput = None
if dmc_feed is not None and dmc_running_hours and dmc_running_hours > 0:
    dmc_throughput = dmc_feed / dmc_running_hours

feeder_throughput = None
if feeder_running_hours and feeder_running_hours > 0:
    if feeder_running_hours > 0 and dmc_feed is not None:
        feeder_throughput = dmc_feed / feeder_running_hours


# ============================================================
# EXECUTIVE PRODUCTION OVERVIEW
# ============================================================

st.markdown(
    '<div class="section-title">EXECUTIVE PRODUCTION OVERVIEW</div>',
    unsafe_allow_html=True,
)

cards = st.columns(4)

with cards[0]:
    metric_card(
        "Clean Coal Production",
        fmt_tons(clean_coal),
        f"Recovery {fmt_pct(recovery)}",
    )

with cards[1]:
    metric_card(
        "Peas Production",
        fmt_tons(peas),
        f"{fmt_pct(peas_share)} of clean coal",
    )

with cards[2]:
    metric_card(
        "Nuts Production",
        fmt_tons(nuts),
        f"{fmt_pct(nuts_share)} of clean coal",
    )

with cards[3]:
    metric_card(
        "DMC Feed",
        fmt_tons(dmc_feed),
        "Material processed",
    )


cards2 = st.columns(4)

with cards2[0]:
    metric_card(
        "Rejects",
        fmt_tons(rejects),
        f"Reject ratio {fmt_pct(reject_ratio)}",
    )

with cards2[1]:
    metric_card(
        "Fines / Ultrafines",
        fmt_tons(fines),
        "Recorded production stream",
    )

with cards2[2]:
    metric_card(
        "DMC Throughput",
        fmt_tph(dmc_throughput),
        f"Design reference {DESIGN_THROUGHPUT_TPH:.0f} tph",
    )

with cards2[3]:
    metric_card(
        "DMC OEE",
        fmt_pct(dmc_oee),
        "From production KPI record",
    )


if derived_feed:
    st.markdown(
        '<div class="info-box">'
        "DMC Feed was not directly available for this period. "
        "The displayed feed value is derived from the available material "
        "streams (clean coal + rejects + fines)."
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# PEAS + NUTS — KEY CLEAN COAL ANALYSIS
# ============================================================

st.markdown(
    '<div class="section-title">CLEAN COAL STREAM ANALYSIS</div>',
    unsafe_allow_html=True,
)

left, right = st.columns(2)

with left:
    st.subheader("Peas vs Nuts Production")

    stream_data = pd.DataFrame(
        {
            "Stream": ["Peas", "Nuts"],
            "Production (t)": [
                peas if peas is not None else 0,
                nuts if nuts is not None else 0,
            ],
        }
    )

    if peas is None and nuts is None:
        st.info("Peas and Nuts production fields are not available.")
    else:
        st.bar_chart(
            stream_data.set_index("Stream"),
            y="Production (t)",
            use_container_width=True,
        )

with right:
    st.subheader("Clean Coal Composition")

    composition = pd.DataFrame(
        {
            "Stream": ["Peas", "Nuts"],
            "Share (%)": [
                peas_share if peas_share is not None else 0,
                nuts_share if nuts_share is not None else 0,
            ],
        }
    )

    if peas_share is None and nuts_share is None:
        st.info("Clean-coal composition cannot be calculated.")
    else:
        st.bar_chart(
            composition.set_index("Stream"),
            y="Share (%)",
            use_container_width=True,
        )


# ============================================================
# MATERIAL BALANCE
# ============================================================

st.markdown(
    '<div class="section-title">MATERIAL BALANCE</div>',
    unsafe_allow_html=True,
)

balance = pd.DataFrame(
    {
        "Stream": [
            "DMC Feed",
            "Clean Coal",
            "Peas",
            "Nuts",
            "Rejects",
            "Fines / Ultrafines",
        ],
        "Tonnes": [
            dmc_feed if dmc_feed is not None else 0,
            clean_coal if clean_coal is not None else 0,
            peas if peas is not None else 0,
            nuts if nuts is not None else 0,
            rejects if rejects is not None else 0,
            fines if fines is not None else 0,
        ],
    }
)

st.bar_chart(
    balance.set_index("Stream"),
    y="Tonnes",
    use_container_width=True,
)


# ============================================================
# CAPACITY / THROUGHPUT PERFORMANCE
# ============================================================

st.markdown(
    '<div class="section-title">CAPACITY & THROUGHPUT PERFORMANCE</div>',
    unsafe_allow_html=True,
)

capacity_pct = None
if dmc_throughput is not None:
    capacity_pct = dmc_throughput / DESIGN_THROUGHPUT_TPH * 100.0

cap1, cap2, cap3 = st.columns(3)

with cap1:
    metric_card(
        "Actual DMC Throughput",
        fmt_tph(dmc_throughput),
        "Calculated from feed / running hours",
    )

with cap2:
    metric_card(
        "Design Throughput",
        f"{DESIGN_THROUGHPUT_TPH:.0f} tph",
        "Current CHPP design reference",
    )

with cap3:
    metric_card(
        "Capacity Utilisation",
        fmt_pct(capacity_pct),
        "Actual throughput ÷ design throughput",
    )

if capacity_pct is not None:
    capacity_df = pd.DataFrame(
        {
            "Metric": ["Actual Throughput", "Design Throughput"],
            "TPH": [dmc_throughput, DESIGN_THROUGHPUT_TPH],
        }
    )

    st.bar_chart(
        capacity_df.set_index("Metric"),
        y="TPH",
        use_container_width=True,
    )


# ============================================================
# EQUIPMENT / PRODUCTION INTERACTION
# ============================================================

st.markdown(
    '<div class="section-title">PRODUCTION & EQUIPMENT PERFORMANCE</div>',
    unsafe_allow_html=True,
)

eq1, eq2, eq3, eq4 = st.columns(4)

with eq1:
    metric_card(
        "DMC Availability",
        fmt_pct(dmc_availability),
        fmt_hours(
            aggregate_sum(period_df, field_map, "dmc_running_hours")
        )
        + " running",
    )

with eq2:
    metric_card(
        "DMC Utilisation",
        fmt_pct(dmc_utilization),
        "From production KPI record",
    )

with eq3:
    metric_card(
        "Feeder Availability",
        fmt_pct(feeder_availability),
        fmt_hours(feeder_running_hours) + " running",
    )

with eq4:
    metric_card(
        "Feeder OEE",
        fmt_pct(feeder_oee),
        "From production KPI record",
    )


# ============================================================
# MULTI-DAY / MONTHLY / YEARLY TREND
# ============================================================

st.markdown(
    '<div class="section-title">PRODUCTION TREND</div>',
    unsafe_allow_html=True,
)

if view == "Day":
    trend_source = df.copy()
    trend_note = (
        "You are viewing a single day. Select Month or Year above "
        "to obtain a multi-day production trend."
    )
else:
    trend_source = period_df.copy()
    trend_note = ""

trend_keys = [
    "clean_coal_tons",
    "peas_tons",
    "nuts_tons",
    "rejects_tons",
    "fines_tons",
]

trend = add_daily_aggregation(
    trend_source,
    field_map,
    trend_keys,
)

if trend.empty or trend["Production Date"].isna().all():
    st.info("No usable production dates are available for trend analysis.")
else:
    trend = trend.set_index("Production Date")

    available_trend_cols = [
        key
        for key in trend_keys
        if key in trend.columns and trend[key].notna().any()
    ]

    rename_map = {
        "clean_coal_tons": "Clean Coal",
        "peas_tons": "Peas",
        "nuts_tons": "Nuts",
        "rejects_tons": "Rejects",
        "fines_tons": "Fines / Ultrafines",
    }

    if available_trend_cols:
        chart_df = trend[available_trend_cols].rename(
            columns=rename_map
        )

        st.line_chart(
            chart_df,
            use_container_width=True,
        )

        if trend_note:
            st.info(trend_note)
    else:
        st.info(
            "No production-stream fields are available for the trend chart."
        )


# ============================================================
# RECOVERY TREND
# ============================================================

st.markdown(
    '<div class="section-title">RECOVERY PERFORMANCE</div>',
    unsafe_allow_html=True,
)

recovery_rows = []

for production_date, group in df.groupby("_production_date"):
    feed = aggregate_sum(group, field_map, "dmc_feed_tons")
    product = aggregate_sum(group, field_map, "clean_coal_tons")

    if product is None:
        p = aggregate_sum(group, field_map, "peas_tons")
        n = aggregate_sum(group, field_map, "nuts_tons")
        if p is not None and n is not None:
            product = p + n

    if feed is not None and feed > 0 and product is not None:
        recovery_rows.append(
            {
                "Production Date": production_date,
                "Recovery (%)": product / feed * 100.0,
            }
        )

recovery_df = pd.DataFrame(recovery_rows)

if recovery_df.empty:
    st.info("Recovery trend cannot be calculated from the available data.")
else:
    recovery_df = recovery_df.set_index("Production Date")
    st.line_chart(
        recovery_df,
        use_container_width=True,
    )

    st.caption(
        f"Reference recovery used for management comparison: "
        f"{REFERENCE_RECOVERY:.1f}%."
    )


# ============================================================
# MANAGEMENT VIEW
# ============================================================

st.markdown(
    '<div class="section-title">MANAGEMENT VIEW</div>',
    unsafe_allow_html=True,
)

if dmc_throughput is not None:
    if dmc_throughput < DESIGN_THROUGHPUT_TPH * 0.85:
        st.markdown(
            f'<div class="insight">'
            f"DMC throughput is {dmc_throughput:.1f} tph, below the "
            f"85% design-performance reference ({DESIGN_THROUGHPUT_TPH * 0.85:.1f} tph). "
            f"Throughput improvement should be investigated."
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="insight">'
            f"DMC throughput is {dmc_throughput:.1f} tph and is at or above "
            f"85% of the {DESIGN_THROUGHPUT_TPH:.0f} tph design reference."
            f"</div>",
            unsafe_allow_html=True,
        )

if recovery is not None:
    if recovery < REFERENCE_RECOVERY:
        st.markdown(
            f'<div class="insight">'
            f"Plant recovery is {recovery:.1f}%, below the "
            f"{REFERENCE_RECOVERY:.1f}% management reference."
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.success(
            f"Plant recovery is {recovery:.1f}%, meeting or exceeding the "
            f"{REFERENCE_RECOVERY:.1f}% management reference."
        )

if peas is not None and nuts is not None:
    st.markdown(
        f'<div class="insight">'
        f"Clean-coal production is split between {peas:,.1f} t of Peas "
        f"and {nuts:,.1f} t of Nuts for the selected period."
        f"</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# DETAILED DATA
# ============================================================

st.markdown(
    '<div class="section-title">DETAILED PRODUCTION DATA</div>',
    unsafe_allow_html=True,
)

with st.expander("View production records used for this analysis"):
    display_df = period_df.copy()

    if "_production_date" in display_df.columns:
        display_df = display_df.drop(columns=["_production_date"])

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# DATA FIELD STATUS
# ============================================================

with st.expander("View production data field status"):
    status_rows = []

    for logical_name, aliases in FIELD_ALIASES.items():
        actual = field_map.get(logical_name)

        status_rows.append(
            {
                "Analytics Parameter": logical_name.replace("_", " ").title(),
                "Database Field": actual if actual else "Not found",
                "Status": "Available" if actual else "Not configured",
            }
        )

    status_df = pd.DataFrame(status_rows)

    st.dataframe(
        status_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "CHPP-PIS • Production Analytics • Uses actual production records "
    "from public.chpp_production_kpis • No quality values are invented."
)


st.markdown(
    """
    <div style="text-align:center; color:#718096; font-size:12px;">
        <strong>Designed & Developed by Levy Mukopeka</strong><br>
        <em>Digital Systems</em>
    </div>
    """,
    unsafe_allow_html=True,
)
