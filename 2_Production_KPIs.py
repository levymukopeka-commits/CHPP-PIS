# ============================================================
# CHPP-PIS | Production Intelligence
# FILE: pages/2_Production_KPIs.py
# COMPLETE REPLACEMENT
#
# Main improvements:
# 1. Day / Month / Year reporting period selector
# 2. Peas and Nuts promoted to Executive KPIs
# 3. Correct period aggregation for tonnes, hours, throughput,
#    availability, utilisation, recovery and OEE
# 4. Daily throughput trend within the selected month/year
# 5. Robust handling of Supabase column names
# 6. No page-link path errors for the current CHPP-PIS structure
# ============================================================

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

from auth import require_login, show_user_sidebar

# ============================================================
# AUTHENTICATION
# ============================================================

user = require_login(
    allowed_roles=[
        "Administrator",
        "Management",
        "Supervisor",
        "Operator",
        "Viewer",
    ]
)

show_user_sidebar()


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="CHPP Production Intelligence",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TABLE_NAME = "chpp_production_kpis"

# Design capacities
DMC_DESIGN_TPH = 200.0
FEEDER_DESIGN_TPH = 400.0

# Management reference
OEE_REFERENCE = 85.0


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background: #080c12;
    }

    [data-testid="stSidebar"] {
        background: #0d131b;
        border-right: 1px solid #263342;
    }

    .block-container {
        max-width: 1450px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    [data-testid="stMetric"] {
        background: #111923;
        border: 1px solid #263342;
        border-radius: 12px;
        padding: 14px 16px;
    }

    [data-testid="stMetricLabel"] {
        color: #91a4ba;
    }

    [data-testid="stMetricValue"] {
        color: #f8fafc;
    }

    div[data-testid="stExpander"] {
        border: 1px solid #263342;
        border-radius: 10px;
    }

    .section-label {
        color: #6ea8ff;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        margin-top: 1.2rem;
        margin-bottom: 0.7rem;
    }

    .period-note {
        color: #91a4ba;
        font-size: 0.85rem;
        margin-top: -0.35rem;
        margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SUPABASE
# ============================================================

@st.cache_resource
def get_supabase():
    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL is missing from .env")

    if not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_KEY is missing from .env")

    return create_client(SUPABASE_URL, SUPABASE_KEY)


@st.cache_data(ttl=30)
def load_production_data():
    client = get_supabase()

    result = (
        client
        .table(TABLE_NAME)
        .select("*")
        .order("production_date", desc=False)
        .execute()
    )

    records = result.data or []

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    df.columns = [
        str(column).strip().lower()
        for column in df.columns
    ]

    if "production_date" in df.columns:
        df["production_date"] = pd.to_datetime(
            df["production_date"],
            errors="coerce",
        )

    for column in df.columns:
        if column != "production_date":
            converted = pd.to_numeric(
                df[column],
                errors="coerce",
            )
            if converted.notna().sum() > 0:
                df[column] = converted

    return df


# ============================================================
# COLUMN ALIASES
# ============================================================

ALIASES = {
    "dmc_feed": [
        "feed_to_dmc_tons",
        "feed_to_dmc",
        "dmc_feed_tons",
        "dmc_feed",
    ],
    "feeder_tons": [
        "feeder_tons",
        "feed_tons",
        "total_processed",
    ],
    "peas": [
        "peas_tons",
        "peas",
    ],
    "nuts": [
        "nuts_tons",
        "nuts",
    ],
    "rejects": [
        "rejects_tons",
        "rejects",
    ],
    "fines": [
        "fines_belt_tons",
        "ultrafines_tons",
        "fines_tons",
        "fines_belt",
        "ultrafines",
    ],
    "planned_hours": [
        "planned_hours",
        "planned_operating_hours",
    ],
    "feeder_running": [
        "feeder_running_hours",
        "feeder_hours",
    ],
    "dmc_running": [
        "dmc_running_hours",
        "dmc_hours",
    ],
    "quality_factor": [
        "quality_factor",
        "quality",
        "quality_percentage",
    ],
}


def first_existing(row, names, default=0.0):
    """Return the first valid numeric value found in a row."""
    for name in names:
        if name in row.index:
            value = row[name]

            if pd.notna(value):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass

    return float(default)


def series_from_aliases(df, names):
    """Return a numeric series from the first matching column."""
    for name in names:
        if name in df.columns:
            return pd.to_numeric(
                df[name],
                errors="coerce",
            ).fillna(0.0)

    return pd.Series(
        0.0,
        index=df.index,
        dtype=float,
    )


def normalise_quality(value):
    """
    Accept either:
      0.98 -> 98%
      98   -> 98%
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 100.0

    if value <= 0:
        return 0.0

    if value <= 1:
        value *= 100.0

    return max(0.0, min(value, 100.0))


# ============================================================
# PREPARE RAW NUMERIC COLUMNS
# ============================================================

def prepare_numeric_columns(df):
    work = df.copy()

    work["dmc_feed"] = series_from_aliases(
        work,
        ALIASES["dmc_feed"],
    )

    work["feeder_tons"] = series_from_aliases(
        work,
        ALIASES["feeder_tons"],
    )

    work["peas"] = series_from_aliases(
        work,
        ALIASES["peas"],
    )

    work["nuts"] = series_from_aliases(
        work,
        ALIASES["nuts"],
    )

    work["rejects"] = series_from_aliases(
        work,
        ALIASES["rejects"],
    )

    work["fines"] = series_from_aliases(
        work,
        ALIASES["fines"],
    )

    work["planned_hours"] = series_from_aliases(
        work,
        ALIASES["planned_hours"],
    )

    work["feeder_running"] = series_from_aliases(
        work,
        ALIASES["feeder_running"],
    )

    work["dmc_running"] = series_from_aliases(
        work,
        ALIASES["dmc_running"],
    )

    quality_source = series_from_aliases(
        work,
        ALIASES["quality_factor"],
    )

    # If no quality column exists, use 100%.
    quality_names_present = [
        name
        for name in ALIASES["quality_factor"]
        if name in work.columns
    ]

    if not quality_names_present:
        work["quality"] = 100.0
    else:
        work["quality"] = quality_source.apply(
            normalise_quality
        )

    # Negative physical values are not meaningful.
    physical_columns = [
        "dmc_feed",
        "feeder_tons",
        "peas",
        "nuts",
        "rejects",
        "fines",
        "planned_hours",
        "feeder_running",
        "dmc_running",
    ]

    for column in physical_columns:
        work[column] = work[column].clip(lower=0.0)

    return work


# ============================================================
# PERIOD HELPERS
# ============================================================

def get_period_options(df):
    dates = (
        df["production_date"]
        .dropna()
        .dt.date
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    months = (
        df["production_date"]
        .dropna()
        .dt.to_period("M")
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    years = (
        df["production_date"]
        .dropna()
        .dt.year
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    return dates, months, years


def filter_by_period(df, period_type, selection):
    """
    Return the records belonging to the selected reporting period.
    """
    if period_type == "Day":
        mask = df["production_date"].dt.date == selection

    elif period_type == "Month":
        mask = (
            df["production_date"].dt.to_period("M")
            == selection
        )

    else:
        mask = (
            df["production_date"].dt.year
            == int(selection)
        )

    return df.loc[mask].copy()


def period_label(period_type, selection):
    if period_type == "Day":
        return selection.strftime("%d %b %Y")

    if period_type == "Month":
        return selection.strftime("%B %Y")

    return str(selection)


# ============================================================
# PERIOD KPI CALCULATION
# ============================================================

def calculate_period_kpis(period_df):
    """
    Calculate KPIs from the complete selected period.

    Tonnes and hours are summed.
    Throughput is total tonnes / total running hours.
    Availability is total running hours / total planned hours.
    Utilisation is throughput / design capacity.
    OEE = Availability x Performance x Quality.
    Recovery = Clean Coal / DMC Feed.
    """

    if period_df.empty:
        return {
            "dmc_feed": 0.0,
            "feeder_tons": 0.0,
            "peas": 0.0,
            "nuts": 0.0,
            "rejects": 0.0,
            "fines": 0.0,
            "clean_coal": 0.0,
            "planned_hours": 0.0,
            "feeder_running": 0.0,
            "dmc_running": 0.0,
            "feeder_tph": 0.0,
            "dmc_tph": 0.0,
            "feeder_availability": 0.0,
            "dmc_availability": 0.0,
            "feeder_utilisation": 0.0,
            "dmc_utilisation": 0.0,
            "feeder_oee": 0.0,
            "dmc_oee": 0.0,
            "quality": 100.0,
            "recovery": 0.0,
            "reject_ratio": 0.0,
            "feeder_downtime": 0.0,
            "dmc_downtime": 0.0,
        }

    # Total production / material
    dmc_feed = period_df["dmc_feed"].sum()
    feeder_tons = period_df["feeder_tons"].sum()
    peas = period_df["peas"].sum()
    nuts = period_df["nuts"].sum()
    rejects = period_df["rejects"].sum()
    fines = period_df["fines"].sum()

    clean_coal = peas + nuts

    # Total time
    planned_hours = period_df["planned_hours"].sum()
    feeder_running = period_df["feeder_running"].sum()
    dmc_running = period_df["dmc_running"].sum()

    # Weighted average quality, weighted by DMC feed where possible.
    if dmc_feed > 0 and period_df["dmc_feed"].sum() > 0:
        quality = (
            (period_df["quality"] * period_df["dmc_feed"]).sum()
            / dmc_feed
        )
    else:
        quality = period_df["quality"].mean()

    quality = normalise_quality(quality)

    # Throughput
    feeder_tph = (
        feeder_tons / feeder_running
        if feeder_running > 0
        else 0.0
    )

    dmc_tph = (
        dmc_feed / dmc_running
        if dmc_running > 0
        else 0.0
    )

    # Availability
    if planned_hours > 0:
        feeder_availability = (
            feeder_running / planned_hours * 100.0
        )
        dmc_availability = (
            dmc_running / planned_hours * 100.0
        )
    else:
        feeder_availability = 0.0
        dmc_availability = 0.0

    feeder_availability = max(
        0.0,
        min(feeder_availability, 100.0),
    )

    dmc_availability = max(
        0.0,
        min(dmc_availability, 100.0),
    )

    # Utilisation may exceed 100% if actual throughput exceeds design.
    feeder_utilisation = (
        feeder_tph / FEEDER_DESIGN_TPH * 100.0
    )

    dmc_utilisation = (
        dmc_tph / DMC_DESIGN_TPH * 100.0
    )

    feeder_utilisation = max(
        0.0,
        feeder_utilisation,
    )

    dmc_utilisation = max(
        0.0,
        dmc_utilisation,
    )

    # OEE performance component is capped at 100%.
    feeder_performance = min(
        feeder_utilisation,
        100.0,
    )

    dmc_performance = min(
        dmc_utilisation,
        100.0,
    )

    feeder_oee = (
        feeder_availability
        * feeder_performance
        * quality
        / 10000.0
    )

    dmc_oee = (
        dmc_availability
        * dmc_performance
        * quality
        / 10000.0
    )

    # Recovery and rejects
    if dmc_feed > 0:
        recovery = (
            clean_coal / dmc_feed * 100.0
        )
        reject_ratio = (
            rejects / dmc_feed * 100.0
        )
    else:
        recovery = 0.0
        reject_ratio = 0.0

    # Downtime
    feeder_downtime = max(
        planned_hours - feeder_running,
        0.0,
    )

    dmc_downtime = max(
        planned_hours - dmc_running,
        0.0,
    )

    return {
        "dmc_feed": dmc_feed,
        "feeder_tons": feeder_tons,
        "peas": peas,
        "nuts": nuts,
        "rejects": rejects,
        "fines": fines,
        "clean_coal": clean_coal,
        "planned_hours": planned_hours,
        "feeder_running": feeder_running,
        "dmc_running": dmc_running,
        "feeder_tph": feeder_tph,
        "dmc_tph": dmc_tph,
        "feeder_availability": feeder_availability,
        "dmc_availability": dmc_availability,
        "feeder_utilisation": feeder_utilisation,
        "dmc_utilisation": dmc_utilisation,
        "feeder_oee": feeder_oee,
        "dmc_oee": dmc_oee,
        "quality": quality,
        "recovery": recovery,
        "reject_ratio": reject_ratio,
        "feeder_downtime": feeder_downtime,
        "dmc_downtime": dmc_downtime,
    }


# ============================================================
# PLOTLY THEME
# ============================================================

PAPER = "#0b1118"
GRID = "#263342"
TEXT = "#dbe4ef"
BLUE = "#60a5fa"
GREEN = "#22c55e"
AMBER = "#f59e0b"
RED = "#ef4444"
DARK = "#202b39"


def base_layout(fig, height=340):
    fig.update_layout(
        height=height,
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        font={"color": TEXT},
        margin={
            "l": 45,
            "r": 25,
            "t": 55,
            "b": 45,
        },
    )
    return fig


def make_gauge(value, title):
    value = max(
        0.0,
        min(float(value), 100.0),
    )

    if value < 50:
        bar_color = RED
    elif value < 75:
        bar_color = AMBER
    else:
        bar_color = BLUE

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={
                "suffix": "%",
                "font": {"size": 30},
            },
            title={
                "text": title,
                "font": {"size": 14},
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "#607086",
                },
                "bar": {
                    "color": bar_color,
                },
                "bgcolor": DARK,
                "borderwidth": 0,
                "steps": [
                    {
                        "range": [0, 50],
                        "color": "#17202a",
                    },
                    {
                        "range": [50, 75],
                        "color": "#1c2630",
                    },
                    {
                        "range": [75, 100],
                        "color": "#263342",
                    },
                ],
            },
        )
    )

    fig.update_layout(
        height=285,
        paper_bgcolor=PAPER,
        font={"color": TEXT},
        margin={
            "l": 15,
            "r": 15,
            "t": 40,
            "b": 10,
        },
    )

    return fig


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## 🏭 CHPP-PIS")
    st.caption("Production Intelligence System")
    st.divider()

    st.markdown("### Current Module")
    st.success("📊 Production Intelligence")

    st.divider()

    st.markdown("### Navigation")

    # These paths match the current project structure:
    # CHPP-PIS/app.py
    # CHPP-PIS/pages/01_Production_Input.py
    # CHPP-PIS/pages/2_Production_KPIs.py

    st.page_link(
        "app.py",
        label="⌂  Home",
    )

    st.page_link(
        "pages/01_Production_Input.py",
        label="✎  Production Input",
    )

    st.divider()

    st.caption(
        "Daily plant performance, equipment effectiveness "
        "and production analytics."
    )


# ============================================================
# LOAD DATA
# ============================================================

try:
    df = load_production_data()
except Exception as exc:
    st.error(
        "Unable to load production data from Supabase."
    )
    st.exception(exc)
    st.stop()


if df.empty:
    st.title("🏭 CHPP Production Intelligence")
    st.info(
        "No production records were found in "
        f"'{TABLE_NAME}'."
    )
    st.stop()


if "production_date" not in df.columns:
    st.error(
        "The Supabase table does not contain "
        "'production_date'."
    )
    st.write("Columns returned by Supabase:")
    st.write(list(df.columns))
    st.stop()


df = prepare_numeric_columns(df)

df = df[
    df["production_date"].notna()
].copy()

if df.empty:
    st.error(
        "No valid production dates were found."
    )
    st.stop()

df = df.sort_values(
    "production_date"
).reset_index(drop=True)


# ============================================================
# HEADER
# ============================================================

title_col, status_col = st.columns([7, 1])

with title_col:
    st.title("🏭 CHPP Production Intelligence")
    st.caption(
        "Daily plant performance • equipment effectiveness • "
        "production analytics"
    )

with status_col:
    st.success("● SYSTEM ONLINE")


# ============================================================
# REPORTING PERIOD
# ============================================================

st.markdown(
    '<div class="section-label">Reporting Period</div>',
    unsafe_allow_html=True,
)

period_col, selection_col, refresh_col = st.columns(
    [1.2, 4.8, 1]
)

with period_col:
    period_type = st.radio(
        "View",
        ["Day", "Month", "Year"],
        horizontal=True,
        key="production_period_type",
    )

valid_dates, valid_months, valid_years = (
    get_period_options(df)
)

# IMPORTANT:
# Use a real calendar date picker rather than a selectbox containing
# only dates that already exist in Supabase.
#
# This means the user can select ANY date, month or year from the
# calendar. If there is no production record for that selection,
# the dashboard will clearly report that no data exists.
latest_available_date = df["production_date"].max().date()

with selection_col:
    selected_calendar_date = st.date_input(
        "Select Date",
        value=latest_available_date,
        key="production_calendar_date",
    )

    if period_type == "Day":
        selected_period = selected_calendar_date

    elif period_type == "Month":
        selected_period = pd.Period(
            selected_calendar_date,
            freq="M",
        )

    else:
        selected_period = selected_calendar_date.year

with refresh_col:
    st.write("")

    if st.button(
        "↻ Refresh",
        use_container_width=True,
        key="refresh_production_data",
    ):
        st.cache_data.clear()
        st.rerun()


selected_label = period_label(
    period_type,
    selected_period,
)

period_df = filter_by_period(
    df,
    period_type,
    selected_period,
)

if period_df.empty:
    st.warning(
        f"No production records found for {selected_label}."
    )
    st.info(
        "You can select another date, month or year from the "
        "calendar above. The dashboard only displays KPIs when "
        "production data exists for the selected period."
    )
    st.stop()

period_kpi = calculate_period_kpis(
    period_df
)

st.markdown(
    f'<div class="period-note">'
    f'Showing production performance for '
    f'<strong>{selected_label}</strong> '
    f'({len(period_df)} record(s)).'
    f'</div>',
    unsafe_allow_html=True,
)


# ============================================================
# EXECUTIVE OVERVIEW
# PEAS AND NUTS ARE DELIBERATELY PROMOTED TO TOP KPIs.
# ============================================================

st.markdown(
    '<div class="section-label">Executive Overview</div>',
    unsafe_allow_html=True,
)

k1, k2, k3 = st.columns(3)

with k1:
    st.metric(
        "Clean Coal Production",
        f'{period_kpi["clean_coal"]:,.0f} t',
        f'Recovery {period_kpi["recovery"]:.1f}%',
    )

with k2:
    st.metric(
        "Peas Production",
        f'{period_kpi["peas"]:,.0f} t',
        "Clean coal stream",
    )

with k3:
    st.metric(
        "Nuts Production",
        f'{period_kpi["nuts"]:,.0f} t',
        "Clean coal stream",
    )

k4, k5, k6 = st.columns(3)

with k4:
    st.metric(
        "DMC Throughput",
        f'{period_kpi["dmc_tph"]:,.1f} tph',
        f'{period_kpi["dmc_utilisation"]:.1f}% of design',
    )

with k5:
    st.metric(
        "DMC Availability",
        f'{period_kpi["dmc_availability"]:.1f}%',
        f'{period_kpi["dmc_running"]:.2f} h running',
    )

with k6:
    st.metric(
        "DMC OEE",
        f'{period_kpi["dmc_oee"]:.1f}%',
        f'Quality {period_kpi["quality"]:.1f}%',
    )


# ============================================================
# EQUIPMENT EFFECTIVENESS
# ============================================================

st.markdown(
    '<div class="section-label">Equipment Effectiveness</div>',
    unsafe_allow_html=True,
)

g1, g2, g3 = st.columns([1, 1, 1])

with g1:
    st.plotly_chart(
        make_gauge(
            period_kpi["feeder_oee"],
            "FEEDER OEE",
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )

with g2:
    st.plotly_chart(
        make_gauge(
            period_kpi["dmc_oee"],
            "DMC OEE",
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )

with g3:
    st.subheader("Operating Health")

    st.metric(
        "Plant Recovery",
        f'{period_kpi["recovery"]:.1f}%',
    )

    st.metric(
        "Reject Ratio",
        f'{period_kpi["reject_ratio"]:.1f}%',
    )

    st.metric(
        "DMC Downtime",
        f'{period_kpi["dmc_downtime"]:.2f} h',
    )


# ============================================================
# THROUGHPUT PERFORMANCE
# ============================================================

st.markdown(
    '<div class="section-label">Throughput Performance</div>',
    unsafe_allow_html=True,
)

c1, c2 = st.columns(2)

with c1:
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=["Feeder", "DMC"],
            y=[
                period_kpi["feeder_tph"],
                period_kpi["dmc_tph"],
            ],
            text=[
                f'{period_kpi["feeder_tph"]:.1f}',
                f'{period_kpi["dmc_tph"]:.1f}',
            ],
            textposition="outside",
            marker_color=BLUE,
        )
    )

    fig.update_yaxes(
        title="TPH",
        gridcolor=GRID,
    )

    fig.update_xaxes(
        showgrid=False,
    )

    fig.update_layout(
        title="Actual Throughput",
        showlegend=False,
    )

    base_layout(fig)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )


with c2:
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Availability",
            x=["Feeder", "DMC"],
            y=[
                period_kpi["feeder_availability"],
                period_kpi["dmc_availability"],
            ],
            marker_color=BLUE,
        )
    )

    fig.add_trace(
        go.Bar(
            name="Utilisation",
            x=["Feeder", "DMC"],
            y=[
                min(period_kpi["feeder_utilisation"], 110),
                min(period_kpi["dmc_utilisation"], 110),
            ],
            marker_color=GREEN,
        )
    )

    fig.update_yaxes(
        title="Percentage",
        range=[0, 110],
        gridcolor=GRID,
    )

    fig.update_xaxes(
        showgrid=False,
    )

    fig.update_layout(
        title="Availability vs Utilisation",
        barmode="group",
        legend={
            "orientation": "h",
            "y": -0.18,
        },
    )

    base_layout(fig)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )


# ============================================================
# PRODUCTION ANALYTICS
# ============================================================

st.markdown(
    '<div class="section-label">Production Analytics</div>',
    unsafe_allow_html=True,
)

s1, s2 = st.columns(2)

stream_names = [
    "Peas",
    "Nuts",
    "Rejects",
    "Fines Belt",
]

stream_values = [
    period_kpi["peas"],
    period_kpi["nuts"],
    period_kpi["rejects"],
    period_kpi["fines"],
]

with s1:
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=stream_names,
            y=stream_values,
            text=[
                f"{value:,.0f} t"
                for value in stream_values
            ],
            textposition="outside",
            marker_color=BLUE,
        )
    )

    fig.update_yaxes(
        title="Tonnes",
        gridcolor=GRID,
    )

    fig.update_xaxes(
        showgrid=False,
    )

    fig.update_layout(
        title="Production Stream Mix",
        showlegend=False,
    )

    base_layout(fig)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )


with s2:
    # Do not show zero-value streams in the pie chart.
    pie_values = []
    pie_labels = []

    for label, value in zip(
        stream_names,
        stream_values,
    ):
        if value > 0:
            pie_labels.append(label)
            pie_values.append(value)

    if pie_values:
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=pie_labels,
                    values=pie_values,
                    hole=0.58,
                    textinfo="label+percent",
                )
            ]
        )

        fig.update_layout(
            title="Material Distribution",
        )

        base_layout(fig)

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False},
        )
    else:
        st.info(
            "No production stream quantities available "
            "for this period."
        )


# ============================================================
# MATERIAL BALANCE
# ============================================================

st.markdown(
    '<div class="section-label">Material Balance</div>',
    unsafe_allow_html=True,
)

b1, b2, b3, b4 = st.columns(4)

with b1:
    st.metric(
        "DMC Feed",
        f'{period_kpi["dmc_feed"]:,.0f} t',
    )

with b2:
    st.metric(
        "Clean Coal",
        f'{period_kpi["clean_coal"]:,.0f} t',
    )

with b3:
    st.metric(
        "Rejects",
        f'{period_kpi["rejects"]:,.0f} t',
    )

with b4:
    st.metric(
        "Ultrafines",
        f'{period_kpi["fines"]:,.0f} t',
    )


# ============================================================
# OEE COMPARISON
# ============================================================

st.markdown(
    '<div class="section-label">Equipment Performance</div>',
    unsafe_allow_html=True,
)

fig = go.Figure()

fig.add_trace(
    go.Bar(
        x=["Feeder", "DMC"],
        y=[
            period_kpi["feeder_oee"],
            period_kpi["dmc_oee"],
        ],
        text=[
            f'{period_kpi["feeder_oee"]:.1f}%',
            f'{period_kpi["dmc_oee"]:.1f}%',
        ],
        textposition="outside",
        marker_color=BLUE,
    )
)

fig.add_hline(
    y=OEE_REFERENCE,
    line_dash="dash",
    line_color=GREEN,
    annotation_text=f"{OEE_REFERENCE:.0f}% reference",
    annotation_position="top right",
)

fig.update_yaxes(
    title="OEE (%)",
    range=[0, 100],
    gridcolor=GRID,
)

fig.update_xaxes(
    showgrid=False,
)

fig.update_layout(
    title="Overall Equipment Effectiveness",
    showlegend=False,
)

base_layout(
    fig,
    height=360,
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={"displayModeBar": False},
)


# ============================================================
# PRODUCTION TREND
# ============================================================

st.markdown(
    '<div class="section-label">Production Trend</div>',
    unsafe_allow_html=True,
)

trend = df.copy()

trend["dmc_tph"] = 0.0
trend["feeder_tph"] = 0.0

dmc_mask = trend["dmc_running"] > 0
feeder_mask = trend["feeder_running"] > 0

trend.loc[dmc_mask, "dmc_tph"] = (
    trend.loc[dmc_mask, "dmc_feed"]
    / trend.loc[dmc_mask, "dmc_running"]
)

trend.loc[feeder_mask, "feeder_tph"] = (
    trend.loc[feeder_mask, "feeder_tons"]
    / trend.loc[feeder_mask, "feeder_running"]
)

# For Month/Year, show the trend inside the selected period.
# For Day, show the latest 14 available production days ending
# at the selected day so the user still gets useful context.
if period_type == "Day":
    trend_source = trend[
        trend["production_date"].dt.date <= selected_period
    ].copy()

    unique_days = (
        trend_source["production_date"]
        .dt.normalize()
        .drop_duplicates()
        .sort_values()
        .tail(14)
    )

    trend_source = trend_source[
        trend_source["production_date"]
        .dt.normalize()
        .isin(unique_days)
    ].copy()

elif period_type == "Month":
    trend_source = trend[
        trend["production_date"].dt.to_period("M")
        == selected_period
    ].copy()

else:
    trend_source = trend[
        trend["production_date"].dt.year
        == int(selected_period)
    ].copy()


if not trend_source.empty:
    daily_trend = (
        trend_source
        .assign(
            trend_date=trend_source[
                "production_date"
            ].dt.date
        )
        .groupby(
            "trend_date",
            as_index=False,
        )
        .agg(
            DMC_TPH=("dmc_tph", "mean"),
            Feeder_TPH=("feeder_tph", "mean"),
        )
        .sort_values("trend_date")
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=daily_trend["trend_date"],
            y=daily_trend["DMC_TPH"],
            mode="lines+markers",
            name="DMC",
            line={
                "color": BLUE,
                "width": 3,
            },
        )
    )

    fig.add_trace(
        go.Scatter(
            x=daily_trend["trend_date"],
            y=daily_trend["Feeder_TPH"],
            mode="lines+markers",
            name="Feeder",
            line={
                "color": GREEN,
                "width": 3,
            },
        )
    )

    fig.update_yaxes(
        title="TPH",
        gridcolor=GRID,
    )

    fig.update_xaxes(
        title="Production Date",
        showgrid=False,
    )

    fig.update_layout(
        title=(
            "Daily Throughput Trend"
            if period_type != "Day"
            else "Recent Throughput Trend"
        ),
        hovermode="x unified",
        legend={
            "orientation": "h",
        },
    )

    base_layout(
        fig,
        height=380,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )

else:
    st.info(
        "Not enough throughput data to display the trend."
    )


# ============================================================
# MANAGEMENT VIEW
# ============================================================

st.markdown(
    '<div class="section-label">Management View</div>',
    unsafe_allow_html=True,
)

messages = []

if period_kpi["dmc_oee"] >= OEE_REFERENCE:
    messages.append(
        (
            "success",
            f'DMC OEE is strong at '
            f'{period_kpi["dmc_oee"]:.1f}%.',
        )
    )
elif period_kpi["dmc_oee"] >= 70:
    messages.append(
        (
            "warning",
            f'DMC OEE is '
            f'{period_kpi["dmc_oee"]:.1f}%. '
            "Improvement opportunity exists.",
        )
    )
else:
    messages.append(
        (
            "error",
            f'DMC OEE is low at '
            f'{period_kpi["dmc_oee"]:.1f}%. '
            "Investigate equipment and operating losses.",
        )
    )

if period_kpi["dmc_availability"] < 80:
    messages.append(
        (
            "warning",
            f'DMC availability is '
            f'{period_kpi["dmc_availability"]:.1f}%. '
            "Downtime requires attention.",
        )
    )

if period_kpi["reject_ratio"] > 30:
    messages.append(
        (
            "warning",
            f'Reject ratio is '
            f'{period_kpi["reject_ratio"]:.1f}%.',
        )
    )

if period_kpi["recovery"] >= 60:
    messages.append(
        (
            "success",
            f'Plant recovery is '
            f'{period_kpi["recovery"]:.1f}%.',
        )
    )
else:
    messages.append(
        (
            "warning",
            f'Plant recovery is '
            f'{period_kpi["recovery"]:.1f}%.',
        )
    )

# Peas/Nuts visibility for management.
if period_kpi["peas"] > 0:
    messages.append(
        (
            "success",
            f'Peas production: '
            f'{period_kpi["peas"]:,.0f} t.',
        )
    )

if period_kpi["nuts"] > 0:
    messages.append(
        (
            "success",
            f'Nuts production: '
            f'{period_kpi["nuts"]:,.0f} t.',
        )
    )

for level, message in messages:
    if level == "success":
        st.success(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.error(message)


# ============================================================
# DETAILED KPI VALUES
# ============================================================

with st.expander("View detailed KPI values"):
    detail_data = {
        "Parameter": [
            "Reporting Period",
            "Records in Period",
            "DMC Feed",
            "Clean Coal",
            "Peas",
            "Nuts",
            "Rejects",
            "Fines / Ultrafines",
            "Feeder Throughput",
            "DMC Throughput",
            "Feeder Availability",
            "DMC Availability",
            "Feeder Utilisation",
            "DMC Utilisation",
            "Feeder OEE",
            "DMC OEE",
            "Quality Factor",
            "Plant Recovery",
            "Reject Ratio",
            "Feeder Downtime",
            "DMC Downtime",
        ],
        "Value": [
            selected_label,
            f"{len(period_df):,}",
            f'{period_kpi["dmc_feed"]:,.2f} t',
            f'{period_kpi["clean_coal"]:,.2f} t',
            f'{period_kpi["peas"]:,.2f} t',
            f'{period_kpi["nuts"]:,.2f} t',
            f'{period_kpi["rejects"]:,.2f} t',
            f'{period_kpi["fines"]:,.2f} t',
            f'{period_kpi["feeder_tph"]:.2f} tph',
            f'{period_kpi["dmc_tph"]:.2f} tph',
            f'{period_kpi["feeder_availability"]:.2f}%',
            f'{period_kpi["dmc_availability"]:.2f}%',
            f'{period_kpi["feeder_utilisation"]:.2f}%',
            f'{period_kpi["dmc_utilisation"]:.2f}%',
            f'{period_kpi["feeder_oee"]:.2f}%',
            f'{period_kpi["dmc_oee"]:.2f}%',
            f'{period_kpi["quality"]:.2f}%',
            f'{period_kpi["recovery"]:.2f}%',
            f'{period_kpi["reject_ratio"]:.2f}%',
            f'{period_kpi["feeder_downtime"]:.2f} h',
            f'{period_kpi["dmc_downtime"]:.2f} h',
        ],
    }

    st.dataframe(
        pd.DataFrame(detail_data),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "CHPP-PIS • Production Intelligence System"
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
