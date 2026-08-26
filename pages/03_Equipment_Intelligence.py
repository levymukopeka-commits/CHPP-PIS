from __future__ import annotations


import os
from pathlib import Path
from datetime import date, datetime
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = Any


# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="CHPP-PIS | Equipment Intelligence",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# AUTHENTICATION
# =============================================================================

from auth import require_login, show_user_sidebar

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


# =============================================================================
# CONSTANTS
# =============================================================================

APP_NAME = "CHPP-PIS"
PAGE_TITLE = "Equipment Intelligence"
PRODUCTION_TABLE = "chpp_production_kpis"

# Expected plant/design references. These are display references only and are
# deliberately kept separate from measured database values.
DMC_DESIGN_TPH = 200.0
FEEDER_DESIGN_TPH = 400.0
OEE_REFERENCE = 85.0

# Common aliases. The loader will find whichever matching column exists.
ALIASES = {
    "date": [
        "production_date",
        "date",
        "productiondate",
        "prod_date",
        "record_date",
    ],
    "feeder_throughput": [
        "feeder_throughput",
        "feeder_actual",
        "feeder_tph",
        "feeder_rate",
        "feed_rate",
        "feeder_rate_tph",
    ],
    "feeder_tons": [
        "feeder_tons",
        "feed_tons",
        "total_processed",
    ],
    "dmc_throughput": [
        "dmc_throughput",
        "dmc_actual",
        "dmc_tph",
        "dmc_rate",
        "dmc_feed_rate",
    ],
    "dmc_tons": [
        "feed_to_dmc_tons",
        "feed_to_dmc",
        "dmc_feed_tons",
        "dmc_feed",
    ],
    "feeder_downtime": [
        "feeder_downtime",
        "feeder_downtime_hours",
        "feeder_down_hours",
        "feeder_downtime_h",
    ],
    "dmc_downtime": [
        "dmc_downtime",
        "dmc_downtime_hours",
        "dmc_down_hours",
        "dmc_downtime_h",
    ],
    "feeder_planned_hours": [
        "feeder_planned_hours",
        "feeder_available_hours",
        "feeder_scheduled_hours",
        "feeder_plan_hours",
    ],
    "dmc_planned_hours": [
        "dmc_planned_hours",
        "dmc_available_hours",
        "dmc_scheduled_hours",
        "dmc_plan_hours",
    ],
    "feeder_running_hours": [
        "feeder_running_hours",
        "feeder_run_hours",
        "feeder_operating_hours",
    ],
    "dmc_running_hours": [
        "dmc_running_hours",
        "dmc_run_hours",
        "dmc_operating_hours",
    ],
    "feeder_availability": [
        "feeder_availability",
        "feeder_availability_pct",
        "feeder_availability_percent",
    ],
    "dmc_availability": [
        "dmc_availability",
        "dmc_availability_pct",
        "dmc_availability_percent",
    ],
    "feeder_utilisation": [
        "feeder_utilisation",
        "feeder_utilization",
        "feeder_utilisation_pct",
        "feeder_utilization_pct",
        "feeder_utilisation_percent",
    ],
    "dmc_utilisation": [
        "dmc_utilisation",
        "dmc_utilization",
        "dmc_utilisation_pct",
        "dmc_utilization_pct",
        "dmc_utilisation_percent",
    ],
    "feeder_oee": [
        "feeder_oee",
        "feeder_oee_pct",
        "feeder_oee_percent",
    ],
    "dmc_oee": [
        "dmc_oee",
        "dmc_oee_pct",
        "dmc_oee_percent",
    ],
    "feeder_stoppages": [
        "feeder_stoppages",
        "feeder_stop_count",
        "feeder_stops",
        "feeder_number_of_stoppages",
    ],
    "dmc_stoppages": [
        "dmc_stoppages",
        "dmc_stop_count",
        "dmc_stops",
        "dmc_number_of_stoppages",
    ],
}


# =============================================================================
# STYLE
# =============================================================================

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1500px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        .hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            margin-bottom: 10px;
        }

        .hero-title {
            font-size: 42px;
            font-weight: 800;
            letter-spacing: -1px;
            margin: 0;
            line-height: 1.1;
        }
        .chpp-trademark {
    color: #60a5fa;
    font-size: 14px;
    font-weight: 600;
    margin-top: 8px;
    margin-bottom: 4px;
}

        .hero-subtitle {
            color: #8d98a8;
            margin-top: 8px;
            font-size: 14px;
        }

        .status {
            border: 1px solid rgba(34,197,94,.35);
            background: rgba(34,197,94,.10);
            color: #4ade80;
            border-radius: 999px;
            padding: 9px 16px;
            font-size: 13px;
            font-weight: 700;
            white-space: nowrap;
        }

        .section-title {
            margin-top: 28px;
            margin-bottom: 12px;
            color: #69a8ff;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 2px;
            text-transform: uppercase;
        }

        .metric-card {
            background: #111923;
            border: 1px solid #263447;
            border-radius: 14px;
            padding: 18px 20px;
            min-height: 120px;
        }

        .metric-label {
            color: #8da5c2;
            font-size: 13px;
            margin-bottom: 8px;
        }

        .metric-value {
            color: #f4f7fb;
            font-size: 29px;
            font-weight: 750;
            line-height: 1.1;
        }

        .metric-note {
            color: #7f91a7;
            font-size: 12px;
            margin-top: 8px;
        }

        .good {
            color: #4ade80 !important;
        }

        .warn {
            color: #fbbf24 !important;
        }

        .bad {
            color: #fb7185 !important;
        }

        .info-box {
            background: #111923;
            border: 1px solid #263447;
            border-radius: 14px;
            padding: 18px 20px;
        }

        .small-muted {
            color: #7f91a7;
            font-size: 12px;
        }

        div[data-testid="stMetric"] {
            background: #111923;
            border: 1px solid #263447;
            border-radius: 14px;
            padding: 16px;
        }

        div[data-testid="stMetricLabel"] {
            color: #8da5c2;
        }

        div[data-testid="stMetricValue"] {
            color: #f4f7fb;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# HELPERS
# =============================================================================

def load_local_env() -> None:
    """
    Load the project's .env file without requiring python-dotenv.

    Streamlit can be launched from a different working directory, so we
    resolve .env relative to this page file:
        CHPP-PIS/.env
    """
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
    ]

    env_file = next((path for path in candidates if path.exists()), None)
    if env_file is None:
        return

    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip()

            if not name:
                continue

            # Remove optional surrounding quotes.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]

            # Do not overwrite a value already supplied by Streamlit/OS.
            if value and not os.getenv(name):
                os.environ[name] = value
    except Exception:
        # The application will display the normal connection error below.
        pass


load_local_env()


def env_value(*names: str) -> Optional[str]:
    """Return the first non-empty environment variable."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def get_supabase() -> Optional[Client]:
    """Create the Supabase client from .env, OS variables, or Streamlit secrets."""
    if create_client is None:
        return None

    url = env_value(
        "SUPABASE_URL",
        "SUPABASE_PROJECT_URL",
        "NEXT_PUBLIC_SUPABASE_URL",
    )
    key = env_value(
        "SUPABASE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    )

    # Also support Streamlit Cloud/local secrets if configured.
    try:
        if not url:
            url = (
                st.secrets.get("SUPABASE_URL")
                or st.secrets.get("SUPABASE_PROJECT_URL")
                or st.secrets.get("NEXT_PUBLIC_SUPABASE_URL")
            )
        if not key:
            key = (
                st.secrets.get("SUPABASE_KEY")
                or st.secrets.get("SUPABASE_ANON_KEY")
                or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
                or st.secrets.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
            )
    except Exception:
        pass

    if not url or not key:
        return None

    try:
        return create_client(str(url).strip(), str(key).strip())
    except Exception:
        return None


def normalize_name(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def find_column(df: pd.DataFrame, aliases: list[str]) -> Optional[str]:
    """Find a dataframe column using case/format-insensitive aliases."""
    if df.empty:
        return None

    normalized = {
        normalize_name(column): column
        for column in df.columns
    }

    for alias in aliases:
        key = normalize_name(alias)
        if key in normalized:
            return normalized[key]

    return None


def numeric_series(df: pd.DataFrame, column: Optional[str]) -> pd.Series:
    if not column or column not in df.columns:
        return pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def safe_mean(series: pd.Series) -> Optional[float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.mean())


def safe_sum(series: pd.Series) -> Optional[float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.sum())


def safe_first(series: pd.Series) -> Optional[float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.iloc[0])


def pct(value: Optional[float]) -> str:
    return "—" if value is None or not np.isfinite(value) else f"{value:.1f}%"


def hours(value: Optional[float]) -> str:
    return "—" if value is None or not np.isfinite(value) else f"{value:.2f} h"


def tph(value: Optional[float]) -> str:
    return "—" if value is None or not np.isfinite(value) else f"{value:.1f} tph"


def tonnes(value: Optional[float]) -> str:
    return "—" if value is None or not np.isfinite(value) else f"{value:,.0f} t"


def status_class(value: Optional[float], good: float, warn: float) -> str:
    if value is None:
        return ""
    if value >= good:
        return "good"
    if value >= warn:
        return "warn"
    return "bad"


def build_metric_card(
    label: str,
    value: str,
    note: str = "",
    css_class: str = "",
) -> str:
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {css_class}">{value}</div>
        <div class="metric-note">{note}</div>
    </div>
    """


def prepare_dates(df: pd.DataFrame) -> tuple[pd.DataFrame, Optional[str]]:
    """Attach a normalized pandas Timestamp date column."""
    date_col = find_column(df, ALIASES["date"])
    if not date_col:
        return df.copy(), None

    result = df.copy()
    parsed = pd.to_datetime(result[date_col], errors="coerce")
    result["_production_date"] = parsed.dt.normalize()
    result = result[result["_production_date"].notna()].copy()
    result = result.sort_values("_production_date").reset_index(drop=True)

    return result, date_col


def fetch_production_data() -> tuple[pd.DataFrame, Optional[str]]:
    """
    Fetch all production rows from the existing chpp_production_kpis table.

    The dataframe is sorted locally after retrieval so this page does not
    depend on a particular database-side date column name.
    """
    client = get_supabase()

    if client is None:
        return pd.DataFrame(), (
            "Supabase environment variables are not available. "
            "Check CHPP-PIS/.env for SUPABASE_URL and SUPABASE_ANON_KEY "
            "(or SUPABASE_KEY)."
        )

    try:
        response = client.table(PRODUCTION_TABLE).select("*").execute()
        rows = response.data or []

        if not rows:
            return pd.DataFrame(), None

        result = pd.DataFrame(rows)

        date_col = find_column(result, ALIASES["date"])
        if date_col:
            result[date_col] = pd.to_datetime(
                result[date_col], errors="coerce"
            )

        return result, None

    except Exception as exc:
        return pd.DataFrame(), str(exc)


def derive_equipment_metrics(
    df: pd.DataFrame,
    equipment: str,
    design_tph: float,
) -> dict[str, Any]:
    """Calculate equipment KPIs from the same fields used by Production KPIs.

    Important: throughput is NOT expected to be a database column. In the
    current CHPP-PIS data model it is correctly calculated as tonnes divided
    by running hours. This prevents the Equipment page from showing 0 tph or
    "Not found" when the underlying production table only stores tonnes and
    running hours.
    """
    prefix = equipment.lower()

    throughput_col = find_column(df, ALIASES[f"{prefix}_throughput"])
    tons_col = find_column(df, ALIASES[f"{prefix}_tons"])
    downtime_col = find_column(df, ALIASES[f"{prefix}_downtime"])
    planned_col = find_column(df, ALIASES[f"{prefix}_planned_hours"])
    running_col = find_column(df, ALIASES[f"{prefix}_running_hours"])
    availability_col = find_column(df, ALIASES[f"{prefix}_availability"])
    utilisation_col = find_column(df, ALIASES[f"{prefix}_utilisation"])
    oee_col = find_column(df, ALIASES[f"{prefix}_oee"])
    stops_col = find_column(df, ALIASES[f"{prefix}_stoppages"])

    explicit_throughput = safe_mean(numeric_series(df, throughput_col))
    tons = safe_sum(numeric_series(df, tons_col))
    downtime = safe_sum(numeric_series(df, downtime_col))
    planned = safe_sum(numeric_series(df, planned_col))
    running = safe_sum(numeric_series(df, running_col))
    explicit_availability = safe_mean(numeric_series(df, availability_col))
    explicit_utilisation = safe_mean(numeric_series(df, utilisation_col))
    explicit_oee = safe_mean(numeric_series(df, oee_col))
    stoppages = safe_sum(numeric_series(df, stops_col))

    if explicit_availability is not None and explicit_availability <= 1.0:
        explicit_availability *= 100.0
    if explicit_utilisation is not None and explicit_utilisation <= 1.0:
        explicit_utilisation *= 100.0
    if explicit_oee is not None and explicit_oee <= 1.0:
        explicit_oee *= 100.0

    # The CHPP production model stores tonnes + running hours. Use that as the
    # authoritative throughput calculation whenever a direct throughput field
    # is absent.
    throughput = explicit_throughput
    throughput_source = throughput_col
    if throughput is None and tons is not None and running is not None and running > 0:
        throughput = tons / running
        throughput_source = "Derived: tonnes / running hours"

    # Same availability logic as the Production KPIs page.
    availability = explicit_availability
    if availability is None and planned is not None and planned > 0 and running is not None:
        availability = max(0.0, min(100.0, running / planned * 100.0))

    if running is None and planned is not None and downtime is not None:
        running = max(0.0, planned - downtime)
        if throughput is None and tons is not None and running > 0:
            throughput = tons / running
            throughput_source = "Derived: tonnes / running hours"

    # Same utilisation concept as Production KPIs: throughput / design.
    utilisation = explicit_utilisation
    if utilisation is None and throughput is not None and design_tph > 0:
        utilisation = max(0.0, throughput / design_tph * 100.0)

    performance = None
    if throughput is not None and design_tph > 0:
        performance = max(0.0, throughput / design_tph * 100.0)

    # Never invent quality. If an explicit OEE is stored, use it. Otherwise
    # leave OEE unconfigured.
    oee = explicit_oee

    return {
        "throughput": throughput,
        "throughput_source": throughput_source,
        "tons": tons,
        "tons_col": tons_col,
        "downtime": downtime,
        "planned_hours": planned,
        "running_hours": running,
        "availability": availability,
        "utilisation": utilisation,
        "performance": performance,
        "oee": oee,
        "stoppages": stoppages,
        "throughput_col": throughput_col,
        "downtime_col": downtime_col,
        "planned_col": planned_col,
        "running_col": running_col,
        "availability_col": availability_col,
        "utilisation_col": utilisation_col,
        "oee_col": oee_col,
        "stoppages_col": stops_col,
    }


def add_derived_throughput_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-record throughput series for trend charts.

    These are derived from the actual production table fields:
    feeder tonnes / feeder running hours
    DMC feed tonnes / DMC running hours
    """
    result = df.copy()

    feeder_tons_col = find_column(result, ALIASES["feeder_tons"])
    feeder_running_col = find_column(result, ALIASES["feeder_running_hours"])
    feeder_direct_col = find_column(result, ALIASES["feeder_throughput"])

    dmc_tons_col = find_column(result, ALIASES["dmc_tons"])
    dmc_running_col = find_column(result, ALIASES["dmc_running_hours"])
    dmc_direct_col = find_column(result, ALIASES["dmc_throughput"])

    if feeder_direct_col:
        result["_feeder_throughput"] = pd.to_numeric(
            result[feeder_direct_col], errors="coerce"
        )
    elif feeder_tons_col and feeder_running_col:
        tons_s = pd.to_numeric(result[feeder_tons_col], errors="coerce")
        run_s = pd.to_numeric(result[feeder_running_col], errors="coerce")
        result["_feeder_throughput"] = tons_s.div(run_s.where(run_s > 0))
    else:
        result["_feeder_throughput"] = np.nan

    if dmc_direct_col:
        result["_dmc_throughput"] = pd.to_numeric(
            result[dmc_direct_col], errors="coerce"
        )
    elif dmc_tons_col and dmc_running_col:
        tons_s = pd.to_numeric(result[dmc_tons_col], errors="coerce")
        run_s = pd.to_numeric(result[dmc_running_col], errors="coerce")
        result["_dmc_throughput"] = tons_s.div(run_s.where(run_s > 0))
    else:
        result["_dmc_throughput"] = np.nan

    return result

def make_gauge(value: Optional[float], title: str, reference: float = 85.0):
    if value is None:
        value = 0.0
        label = "N/A"
    else:
        label = f"{value:.1f}%"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "%", "font": {"size": 30}},
            title={"text": title, "font": {"size": 14}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "#65758b",
                },
                "bar": {
                    "color": (
                        "#ef4444"
                        if value < 60
                        else "#f59e0b"
                        if value < 85
                        else "#22c55e"
                    )
                },
                "bgcolor": "#1d2a3a",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 60], "color": "#192333"},
                    {"range": [60, 85], "color": "#202d3d"},
                    {"range": [85, 100], "color": "#263445"},
                ],
                "threshold": {
                    "line": {"color": "#4ade80", "width": 2},
                    "thickness": 0.8,
                    "value": reference,
                },
            },
        )
    )

    fig.update_layout(
        height=280,
        margin=dict(l=15, r=15, t=45, b=15),
        paper_bgcolor="#0b1017",
        font={"color": "#e8eef7"},
    )
    return fig


def make_bar_chart(
    labels: list[str],
    values: list[float],
    title: str,
    y_title: str,
    reference: Optional[float] = None,
):
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=labels,
            y=values,
            text=[
                f"{v:.1f}"
                for v in values
            ],
            textposition="outside",
            marker_color="#60a5fa",
            name=title,
        )
    )

    if reference is not None:
        fig.add_hline(
            y=reference,
            line_dash="dash",
            line_color="#22c55e",
            annotation_text=f"{reference:.0f} reference",
            annotation_position="top right",
        )

    fig.update_layout(
        title={"text": title, "font": {"size": 16}},
        yaxis_title=y_title,
        xaxis_title="",
        height=360,
        margin=dict(l=45, r=25, t=55, b=45),
        paper_bgcolor="#0b1017",
        plot_bgcolor="#0b1017",
        font={"color": "#e8eef7"},
        legend={"orientation": "h", "y": -0.18},
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#273342")
    return fig


def make_trend_chart(
    df: pd.DataFrame,
    equipment_columns: dict[str, Optional[str]],
    title: str,
):
    """Create a safe daily trend chart from the normalized date column."""
    fig = go.Figure()

    if df.empty or "_production_date" not in df.columns:
        fig.update_layout(
            title=title,
            height=390,
            paper_bgcolor="#0b1017",
            plot_bgcolor="#0b1017",
            font={"color": "#e8eef7"},
        )
        return fig

    for label, column in equipment_columns.items():
        if not column or column not in df.columns:
            continue

        work = df[["_production_date", column]].copy()
        work[column] = pd.to_numeric(work[column], errors="coerce")
        work = work.dropna(subset=["_production_date", column])

        if work.empty:
            continue

        series = (
            work.groupby("_production_date", as_index=False)[column]
            .mean()
        )

        fig.add_trace(
            go.Scatter(
                x=series["_production_date"],
                y=series[column],
                mode="lines+markers",
                name=label,
            )
        )

    fig.update_layout(
        title={"text": title, "font": {"size": 16}},
        height=390,
        margin=dict(l=45, r=25, t=55, b=45),
        paper_bgcolor="#0b1017",
        plot_bgcolor="#0b1017",
        font={"color": "#e8eef7"},
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.18},
    )
    fig.update_xaxes(title="Production Date")
    fig.update_yaxes(title="Value", gridcolor="#273342")
    return fig


# =============================================================================
# HEADER
# =============================================================================

st.markdown(
    """
    <div class="hero">
        <div>
            <div class="hero-title">⚙️ CHPP Equipment Intelligence</div>

<div class="chpp-trademark">
    Designed & Developed by Levy Mukopeka
</div>

<div class="hero-subtitle">
    Equipment effectiveness • downtime • availability • utilisation
    • throughput performance
</div>
        </div>
        <div class="status">● SYSTEM ONLINE</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# LOAD DATA
# =============================================================================

with st.spinner("Loading equipment data..."):
    raw_df, load_error = fetch_production_data()

if load_error:
    st.error(
        "Unable to load production data from Supabase. "
        f"Database message: {load_error}"
    )
    st.info(
        f"This page uses the existing production table. "
        "No new equipment table is required for this version."
    )
    st.stop()

if raw_df.empty:
    st.warning(
        "No production records are currently available. "
        "Enter production data first, then return to Equipment Intelligence."
    )
    st.stop()

df, date_column = prepare_dates(raw_df)

if date_column is None or df.empty:
    st.error(
        "A production date column could not be identified. "
        "Expected a column such as production_date or date."
    )
    st.stop()


# =============================================================================
# REPORTING PERIOD
# =============================================================================

st.markdown(
    '<div class="section-title">Reporting Period</div>',
    unsafe_allow_html=True,
)

view = st.radio(
    "View",
    ["Day", "Month", "Year"],
    horizontal=True,
)

available_dates = sorted(df["_production_date"].dropna().unique())

if not available_dates:
    st.error("No valid production dates were found.")
    st.stop()

min_date = available_dates[0].date()
max_date = available_dates[-1].date()

if view == "Day":
    selected_date = st.date_input(
        "Production Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="equipment_selected_day",
    )

    selected_timestamp = pd.Timestamp(selected_date)
    filtered = df[
        df["_production_date"] == selected_timestamp
    ].copy()
    period_label = selected_timestamp.strftime("%d %b %Y")

elif view == "Month":
    month_options = sorted(
        pd.Series(df["_production_date"].dt.to_period("M").unique())
        .tolist()
    )

    selected_period = st.selectbox(
        "Production Month",
        month_options,
        index=len(month_options) - 1,
        format_func=lambda x: pd.Period(x).strftime("%B %Y"),
        key="equipment_selected_month",
    )

    selected_period = pd.Period(selected_period, freq="M")
    filtered = df[
        df["_production_date"].dt.to_period("M") == selected_period
    ].copy()
    period_label = selected_period.strftime("%B %Y")

else:
    year_options = sorted(
        df["_production_date"].dt.year.dropna().astype(int).unique().tolist()
    )

    selected_year = st.selectbox(
        "Production Year",
        year_options,
        index=len(year_options) - 1,
        key="equipment_selected_year",
    )

    filtered = df[
        df["_production_date"].dt.year == int(selected_year)
    ].copy()
    period_label = str(selected_year)

st.caption(
    f"Showing equipment performance for {period_label} "
    f"({len(filtered)} production record(s))."
)

if filtered.empty:
    st.warning(
        f"No production records are available for {period_label}. "
        "Choose another reporting period."
    )
    st.stop()

# Build per-record throughput values from the existing production fields.
filtered = add_derived_throughput_columns(filtered)


# =============================================================================
# EQUIPMENT METRICS
# =============================================================================

feeder = derive_equipment_metrics(
    filtered,
    "feeder",
    FEEDER_DESIGN_TPH,
)

dmc = derive_equipment_metrics(
    filtered,
    "dmc",
    DMC_DESIGN_TPH,
)


# =============================================================================
# EXECUTIVE EQUIPMENT OVERVIEW
# =============================================================================

st.markdown(
    '<div class="section-title">Equipment Overview</div>',
    unsafe_allow_html=True,
)

overview_cols = st.columns(4)

with overview_cols[0]:
    st.markdown(
        build_metric_card(
            "DMC Throughput",
            tph(dmc["throughput"]),
            f"Design reference: {DMC_DESIGN_TPH:.0f} tph",
            status_class(dmc["throughput"] / DMC_DESIGN_TPH * 100 if dmc["throughput"] is not None else None, 95, 80),
        ),
        unsafe_allow_html=True,
    )

with overview_cols[1]:
    st.markdown(
        build_metric_card(
            "DMC Availability",
            pct(dmc["availability"]),
            hours(dmc["downtime"]) + " downtime" if dmc["downtime"] is not None else "No downtime field configured",
            status_class(dmc["availability"], 85, 75),
        ),
        unsafe_allow_html=True,
    )

with overview_cols[2]:
    st.markdown(
        build_metric_card(
            "DMC Utilisation",
            pct(dmc["utilisation"]),
            hours(dmc["running_hours"]) + " running" if dmc["running_hours"] is not None else "No running-hours field configured",
            status_class(dmc["utilisation"], 85, 70),
        ),
        unsafe_allow_html=True,
    )

with overview_cols[3]:
    oee_note = (
        "Actual OEE from database"
        if dmc["oee"] is not None
        else "OEE requires configured quality data"
    )

    st.markdown(
        build_metric_card(
            "DMC OEE",
            pct(dmc["oee"]),
            oee_note,
            status_class(dmc["oee"], OEE_REFERENCE, 70),
        ),
        unsafe_allow_html=True,
    )


# =============================================================================
# EQUIPMENT HEALTH
# =============================================================================

st.markdown(
    '<div class="section-title">Equipment Health</div>',
    unsafe_allow_html=True,
)

g1, g2, health = st.columns([1, 1, 0.9])

with g1:
    st.plotly_chart(
        make_gauge(
            feeder["oee"],
            "FEEDER OEE",
            OEE_REFERENCE,
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )

with g2:
    st.plotly_chart(
        make_gauge(
            dmc["oee"],
            "DMC OEE",
            OEE_REFERENCE,
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )

with health:
    st.markdown("### Operating Health")

    health_items = [
        ("Feeder Availability", feeder["availability"], "%"),
        ("DMC Availability", dmc["availability"], "%"),
        ("DMC Downtime", dmc["downtime"], " h"),
        ("DMC Stoppages", dmc["stoppages"], ""),
    ]

    for label, value, suffix in health_items:
        if value is None:
            display = "Not configured"
        elif suffix == "%":
            display = f"{value:.1f}%"
        elif suffix == " h":
            display = f"{value:.2f} h"
        else:
            display = f"{value:.0f}"

        st.markdown(
            f"""
            <div class="metric-card" style="margin-bottom:10px;min-height:0;">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="font-size:24px;">{display}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =============================================================================
# THROUGHPUT & AVAILABILITY
# =============================================================================

st.markdown(
    '<div class="section-title">Throughput Performance</div>',
    unsafe_allow_html=True,
)

c1, c2 = st.columns(2)

with c1:
    labels = ["Feeder", "DMC"]
    values = [
        feeder["throughput"] if feeder["throughput"] is not None else 0,
        dmc["throughput"] if dmc["throughput"] is not None else 0,
    ]

    fig = make_bar_chart(
        labels,
        values,
        "Actual Throughput",
        "TPH",
    )

    fig.update_layout(
        yaxis={"range": [0, max(FEEDER_DESIGN_TPH, DMC_DESIGN_TPH) * 1.15]}
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )

with c2:
    availability_values = [
        feeder["availability"] if feeder["availability"] is not None else 0,
        dmc["availability"] if dmc["availability"] is not None else 0,
    ]

    utilisation_values = [
        feeder["utilisation"] if feeder["utilisation"] is not None else 0,
        dmc["utilisation"] if dmc["utilisation"] is not None else 0,
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=["Feeder", "DMC"],
            y=availability_values,
            name="Availability",
            marker_color="#60a5fa",
            text=[f"{v:.1f}%" for v in availability_values],
            textposition="outside",
        )
    )

    fig.add_trace(
        go.Bar(
            x=["Feeder", "DMC"],
            y=utilisation_values,
            name="Utilisation",
            marker_color="#22c55e",
            text=[f"{v:.1f}%" for v in utilisation_values],
            textposition="outside",
        )
    )

    fig.update_layout(
        title={"text": "Availability vs Utilisation", "font": {"size": 16}},
        barmode="group",
        yaxis_title="Percentage",
        yaxis={"range": [0, 110]},
        height=360,
        margin=dict(l=45, r=25, t=55, b=45),
        paper_bgcolor="#0b1017",
        plot_bgcolor="#0b1017",
        font={"color": "#e8eef7"},
        legend={"orientation": "h", "y": -0.18},
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#273342")

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )


# =============================================================================
# DOWNTIME ANALYSIS
# =============================================================================

st.markdown(
    '<div class="section-title">Downtime Analysis</div>',
    unsafe_allow_html=True,
)

d1, d2 = st.columns(2)

with d1:
    downtime_values = [
        feeder["downtime"] if feeder["downtime"] is not None else 0,
        dmc["downtime"] if dmc["downtime"] is not None else 0,
    ]

    fig = make_bar_chart(
        ["Feeder", "DMC"],
        downtime_values,
        "Equipment Downtime",
        "Hours",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )

with d2:
    stoppage_values = [
        feeder["stoppages"] if feeder["stoppages"] is not None else 0,
        dmc["stoppages"] if dmc["stoppages"] is not None else 0,
    ]

    fig = make_bar_chart(
        ["Feeder", "DMC"],
        stoppage_values,
        "Number of Stoppages",
        "Count",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )


# =============================================================================
# TREND ANALYSIS
# =============================================================================

st.markdown(
    '<div class="section-title">Equipment Trends</div>',
    unsafe_allow_html=True,
)

trend_columns = {
    "Feeder Throughput": "_feeder_throughput",
    "DMC Throughput": "_dmc_throughput",
}

if len(filtered) > 1:
    st.plotly_chart(
        make_trend_chart(
            filtered,
            trend_columns,
            "Daily Throughput Trend",
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )
else:
    st.info(
        "The selected period contains one production record. "
        "Select Month or Year to see a multi-day equipment trend."
    )


# =============================================================================
# EQUIPMENT COMPARISON
# =============================================================================

st.markdown(
    '<div class="section-title">Equipment Performance Comparison</div>',
    unsafe_allow_html=True,
)

comparison = pd.DataFrame(
    {
        "Parameter": [
            "Throughput",
            "Availability",
            "Utilisation",
            "Performance vs Design",
            "Downtime",
            "Running Hours",
            "Stoppages",
            "OEE",
        ],
        "Feeder": [
            tph(feeder["throughput"]),
            pct(feeder["availability"]),
            pct(feeder["utilisation"]),
            pct(feeder["performance"]),
            hours(feeder["downtime"]),
            hours(feeder["running_hours"]),
            "—" if feeder["stoppages"] is None else f"{feeder['stoppages']:.0f}",
            pct(feeder["oee"]),
        ],
        "DMC": [
            tph(dmc["throughput"]),
            pct(dmc["availability"]),
            pct(dmc["utilisation"]),
            pct(dmc["performance"]),
            hours(dmc["downtime"]),
            hours(dmc["running_hours"]),
            "—" if dmc["stoppages"] is None else f"{dmc['stoppages']:.0f}",
            pct(dmc["oee"]),
        ],
    }
)

st.dataframe(
    comparison,
    use_container_width=True,
    hide_index=True,
)


# =============================================================================
# DATA CONFIGURATION STATUS
# =============================================================================

st.markdown(
    '<div class="section-title">Equipment Data Configuration</div>',
    unsafe_allow_html=True,
)

config_rows = []

for equipment_name, metrics in [
    ("Feeder", feeder),
    ("DMC", dmc),
]:
    config_rows.extend(
        [
            {
                "Equipment": equipment_name,
                "Parameter": "Throughput",
                "Database field": metrics["throughput_source"] or "Not available",
            },
            {
                "Equipment": equipment_name,
                "Parameter": "Production tonnes",
                "Database field": metrics["tons_col"] or "Not found",
            },
            {
                "Equipment": equipment_name,
                "Parameter": "Downtime",
                "Database field": metrics["downtime_col"] or "Not found",
            },
            {
                "Equipment": equipment_name,
                "Parameter": "Planned hours",
                "Database field": metrics["planned_col"] or "Not found",
            },
            {
                "Equipment": equipment_name,
                "Parameter": "Running hours",
                "Database field": metrics["running_col"] or "Not found",
            },
            {
                "Equipment": equipment_name,
                "Parameter": "Availability",
                "Database field": metrics["availability_col"] or "Derived / not found",
            },
            {
                "Equipment": equipment_name,
                "Parameter": "Utilisation",
                "Database field": metrics["utilisation_col"] or "Derived / not found",
            },
            {
                "Equipment": equipment_name,
                "Parameter": "OEE",
                "Database field": metrics["oee_col"] or "Not configured",
            },
            {
                "Equipment": equipment_name,
                "Parameter": "Stoppages",
                "Database field": metrics["stoppages_col"] or "Not found",
            },
        ]
    )

config_df = pd.DataFrame(config_rows)
st.dataframe(
    config_df,
    use_container_width=True,
    hide_index=True,
)


# =============================================================================
# MANAGEMENT VIEW
# =============================================================================

st.markdown(
    '<div class="section-title">Management View</div>',
    unsafe_allow_html=True,
)

management_messages = []

if dmc["oee"] is not None and dmc["oee"] < OEE_REFERENCE:
    management_messages.append(
        f"DMC OEE is {dmc['oee']:.1f}%, below the {OEE_REFERENCE:.0f}% reference."
    )

if dmc["availability"] is not None and dmc["availability"] < 85:
    management_messages.append(
        f"DMC availability is {dmc['availability']:.1f}%. Downtime should be reviewed."
    )

if dmc["throughput"] is not None and dmc["throughput"] < DMC_DESIGN_TPH * 0.90:
    management_messages.append(
        f"DMC throughput is {dmc['throughput']:.1f} tph, below 90% of the "
        f"{DMC_DESIGN_TPH:.0f} tph design reference."
    )

if dmc["downtime"] is not None and dmc["downtime"] > 2:
    management_messages.append(
        f"DMC downtime is {dmc['downtime']:.2f} h for the selected period."
    )

if feeder["availability"] is not None and feeder["availability"] < 85:
    management_messages.append(
        f"Feeder availability is {feeder['availability']:.1f}%. "
        "Front-end equipment requires attention."
    )

if not management_messages:
    management_messages.append(
        "No major equipment exception was detected from the configured KPIs."
    )

for message in management_messages:
    if any(
        word in message.lower()
        for word in ["below", "downtime", "requires attention"]
    ):
        st.warning(message)
    else:
        st.success(message)


# =============================================================================
# DATA DETAIL
# =============================================================================

with st.expander("View equipment data used for this report"):
    display_columns = []

    for column in [
        date_column,
        feeder["throughput_col"],
        feeder["downtime_col"],
        feeder["availability_col"],
        feeder["utilisation_col"],
        feeder["oee_col"],
        dmc["throughput_col"],
        dmc["downtime_col"],
        dmc["availability_col"],
        dmc["utilisation_col"],
        dmc["oee_col"],
    ]:
        if column and column in filtered.columns and column not in display_columns:
            display_columns.append(column)

    if display_columns:
        detail_df = filtered[display_columns].copy()
        st.dataframe(
            detail_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No equipment-specific fields were found in the selected records.")


# =============================================================================
# FOOTER
# =============================================================================

st.divider()

st.caption(
    "CHPP-PIS • Equipment Intelligence • "
    "Uses existing production records • Throughput is derived from tonnes/running hours when needed • No quality values are invented"
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
