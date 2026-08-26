"""
CHPP-PIS — 05_Management_Intelligence.py
Management Intelligence module.

Purpose
-------
Provide a management-level view of the production and equipment information
already stored in Supabase.

This module:
- Uses the existing CHPP production KPI data model.
- Provides Day / Month / Year reporting.
- Identifies the main operational strengths and attention areas.
- Summarises production, recovery, rejects, throughput, availability,
  utilisation and OEE.
- Uses only values actually available in the database.
- Does NOT invent coal quality values.
- Does NOT calculate OEE using an assumed quality factor.
- Clearly labels derived values.

Expected Supabase table:
    public.chpp_production_kpis
"""

from __future__ import annotations

import os
from typing import Any, Optional

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = Any

try:
    import plotly.graph_objects as go
    import plotly.express as px
except Exception:
    go = None
    px = None


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="CHPP-PIS | Management Intelligence",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# AUTHENTICATION
# ============================================================

from auth import require_login, show_user_sidebar

user = require_login(
    allowed_roles=[
        "Administrator",
        "Management",
        "Supervisor",
        "Viewer",
    ]
)

show_user_sidebar()


# ============================================================
# CONSTANTS
# ============================================================

TABLE_NAME = "chpp_production_kpis"

DMC_DESIGN_TPH = 200.0
FEEDER_DESIGN_TPH = 400.0

REFERENCE_THROUGHPUT_PCT = 85.0
REFERENCE_RECOVERY_PCT = 66.7
REFERENCE_DMC_OEE_PCT = 85.0
REFERENCE_AVAILABILITY_PCT = 85.0

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# ============================================================
# FIELD ALIASES
# ============================================================

FIELD_ALIASES = {
    "production_date": [
        "production_date",
        "date",
        "prod_date",
        "production_day",
    ],
    "dmc_feed_tons": [
        "feed_to_dmc_tons",
        "feed_to_dmc",
        "dmc_feed_tons",
        "dmc_feed",
        "feed_tons",
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
        "fines_belt_tons",
        "fines_belt",
        "fines_tons",
        "ultrafines_tons",
        "ultrafines",
        "ultrafines_tonnes",
    ],
    "feeder_tons": [
        "feeder_tons",
        "feeder_production_tons",
        "feeder_tonnes",
    ],
    "planned_hours": [
        "planned_hours",
        "planned_operating_hours",
    ],
    "feeder_running_hours": [
        "feeder_running_hours",
        "feeder_run_hours",
        "feeder_hours",
    ],
    "dmc_running_hours": [
        "dmc_running_hours",
        "dmc_run_hours",
        "dmc_hours",
    ],
    "dmc_downtime_hours": [
        "dmc_downtime_hours",
        "dmc_downtime",
    ],
    "feeder_downtime_hours": [
        "feeder_downtime_hours",
        "feeder_downtime",
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
    # Quality fields are detected only when they actually exist in the
    # production table. No quality value is invented by this module.
    "feed_ash": [
        "feed_ash",
        "feed_ash_pct",
        "rom_ash",
        "rom_ash_pct",
    ],
    "feed_sulphur": [
        "feed_sulphur",
        "feed_sulfur",
        "feed_sulphur_pct",
        "feed_sulfur_pct",
        "rom_sulphur",
        "rom_sulfur",
    ],
    "peas_ash": [
        "peas_ash",
        "peas_ash_pct",
    ],
    "peas_sulphur": [
        "peas_sulphur",
        "peas_sulfur",
        "peas_sulphur_pct",
        "peas_sulfur_pct",
    ],
    "nuts_ash": [
        "nuts_ash",
        "nuts_ash_pct",
    ],
    "nuts_sulphur": [
        "nuts_sulphur",
        "nuts_sulfur",
        "nuts_sulphur_pct",
        "nuts_sulfur_pct",
    ],
    "clean_coal_ash": [
        "clean_coal_ash",
        "clean_coal_ash_pct",
        "product_ash",
        "product_ash_pct",
    ],
    "clean_coal_sulphur": [
        "clean_coal_sulphur",
        "clean_coal_sulfur",
        "clean_coal_sulphur_pct",
        "clean_coal_sulfur_pct",
        "product_sulphur",
        "product_sulfur",
        "product_sulphur_pct",
        "product_sulfur_pct",
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
        text-align: center;
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
        font-size: 29px;
        font-weight: 800;
        line-height: 1.1;
    }

    .metric-note {
        color: #7f91a7;
        font-size: 12px;
        margin-top: 8px;
    }

    .decision-card {
        background: #111923;
        border: 1px solid #263548;
        border-radius: 12px;
        padding: 18px;
        min-height: 145px;
    }

    .decision-title {
        font-size: 15px;
        font-weight: 800;
        margin-bottom: 8px;
    }

    .decision-text {
        color: #b9c4d2;
        font-size: 13px;
        line-height: 1.5;
    }

    .good {
        color: #35df83;
    }

    .watch {
        color: #f6b94a;
    }

    .attention {
        color: #ff7272;
    }

    .info-box {
        background: #12243a;
        border-left: 4px solid #5ea1ff;
        border-radius: 8px;
        padding: 13px 16px;
        color: #c9d7e8;
        margin-top: 10px;
        margin-bottom: 10px;
    }

    .warning-box {
        background: #302b14;
        border-left: 4px solid #e7b93f;
        border-radius: 8px;
        padding: 13px 16px;
        color: #eee1ad;
        margin-top: 10px;
        margin-bottom: 10px;
    }

    .danger-box {
        background: #321d22;
        border-left: 4px solid #ef6464;
        border-radius: 8px;
        padding: 13px 16px;
        color: #f2c5c5;
        margin-top: 10px;
        margin-bottom: 10px;
    }

    .small-muted {
        color: #7f91a7;
        font-size: 12px;
    }

    div[data-testid="stMetric"] {
        background: #111923;
        border: 1px solid #263548;
        border-radius: 12px;
        padding: 14px;
    }

    div[data-testid="stExpander"] {
        border: 1px solid #263548;
        border-radius: 10px;
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
    if create_client is None:
        raise RuntimeError(
            "The Supabase Python package is not available."
        )

    if not SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is missing from .env"
        )

    if not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_KEY is missing from .env"
        )

    return create_client(SUPABASE_URL, SUPABASE_KEY)


@st.cache_data(ttl=30)
def load_production_data() -> pd.DataFrame:
    client = get_supabase()

    response = (
        client
        .table(TABLE_NAME)
        .select("*")
        .order("production_date", desc=False)
        .execute()
    )

    records = response.data or []

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
# DATA HELPERS
# ============================================================

def normalize_name(value: str) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def find_column(
    df: pd.DataFrame,
    candidates: list[str],
) -> Optional[str]:
    if df.empty:
        return None

    normalized = {
        normalize_name(column): column
        for column in df.columns
    }

    for candidate in candidates:
        key = normalize_name(candidate)
        if key in normalized:
            return normalized[key]

    return None


def build_field_map(df: pd.DataFrame) -> dict[str, Optional[str]]:
    return {
        key: find_column(df, candidates)
        for key, candidates in FIELD_ALIASES.items()
    }


def numeric_sum(
    df: pd.DataFrame,
    column: Optional[str],
) -> Optional[float]:
    if column is None or df.empty:
        return None

    values = pd.to_numeric(
        df[column],
        errors="coerce",
    )

    if values.notna().sum() == 0:
        return None

    return float(values.sum())


def numeric_mean(
    df: pd.DataFrame,
    column: Optional[str],
) -> Optional[float]:
    if column is None or df.empty:
        return None

    values = pd.to_numeric(
        df[column],
        errors="coerce",
    )

    if values.notna().sum() == 0:
        return None

    return float(values.mean())


def percentage_value(
    df: pd.DataFrame,
    column: Optional[str],
) -> Optional[float]:
    value = numeric_mean(df, column)

    if value is None:
        return None

    # Existing CHPP pages store some percentage values as fractions.
    if 0 <= value <= 1:
        value *= 100.0

    return max(0.0, min(value, 100.0))


def aggregate_period(
    df: pd.DataFrame,
    field_map: dict[str, Optional[str]],
) -> dict[str, Optional[float]]:

    result: dict[str, Optional[float]] = {}

    for key in [
        "dmc_feed_tons",
        "clean_coal_tons",
        "peas_tons",
        "nuts_tons",
        "rejects_tons",
        "fines_tons",
        "feeder_tons",
        "planned_hours",
        "feeder_running_hours",
        "dmc_running_hours",
        "dmc_downtime_hours",
        "feeder_downtime_hours",
    ]:
        result[key] = numeric_sum(
            df,
            field_map.get(key),
        )

    for key in [
        "dmc_availability",
        "feeder_availability",
        "dmc_utilization",
        "feeder_utilization",
        "dmc_oee",
        "feeder_oee",
    ]:
        result[key] = percentage_value(
            df,
            field_map.get(key),
        )

    return result


def derive_metrics(
    values: dict[str, Optional[float]],
) -> dict[str, Optional[float]]:

    feed = values["dmc_feed_tons"]
    peas = values["peas_tons"]
    nuts = values["nuts_tons"]
    rejects = values["rejects_tons"]
    fines = values["fines_tons"]

    clean_coal = values["clean_coal_tons"]

    clean_coal_derived = False

    if clean_coal is None and peas is not None and nuts is not None:
        clean_coal = peas + nuts
        clean_coal_derived = True

    derived_feed = False

    if feed is None:
        components = [
            value
            for value in [
                clean_coal,
                rejects,
                fines,
            ]
            if value is not None
        ]

        if components:
            feed = sum(components)
            derived_feed = True

    recovery = None
    reject_ratio = None
    clean_coal_share = None
    peas_share = None
    nuts_share = None

    if feed is not None and feed > 0:

        if clean_coal is not None:
            recovery = (
                clean_coal / feed * 100.0
            )

        if rejects is not None:
            reject_ratio = (
                rejects / feed * 100.0
            )

    if clean_coal is not None and clean_coal > 0:

        if peas is not None:
            peas_share = (
                peas / clean_coal * 100.0
            )

        if nuts is not None:
            nuts_share = (
                nuts / clean_coal * 100.0
            )

    if feed is not None and feed > 0 and clean_coal is not None:
        clean_coal_share = (
            clean_coal / feed * 100.0
        )

    feeder_tph = None
    dmc_tph = None

    feeder_tons = values["feeder_tons"]
    feeder_hours = values["feeder_running_hours"]
    dmc_hours = values["dmc_running_hours"]

    if feeder_tons is not None and feeder_hours:
        if feeder_hours > 0:
            feeder_tph = feeder_tons / feeder_hours

    if feed is not None and dmc_hours:
        if dmc_hours > 0:
            dmc_tph = feed / dmc_hours

    feeder_availability = values["feeder_availability"]
    dmc_availability = values["dmc_availability"]

    if feeder_availability is None:
        planned = values["planned_hours"]
        if planned and planned > 0 and feeder_hours is not None:
            feeder_availability = (
                feeder_hours / planned * 100.0
            )

    if dmc_availability is None:
        planned = values["planned_hours"]
        if planned and planned > 0 and dmc_hours is not None:
            dmc_availability = (
                dmc_hours / planned * 100.0
            )

    feeder_utilization = values["feeder_utilization"]
    dmc_utilization = values["dmc_utilization"]

    if feeder_utilization is None and feeder_tph is not None:
        feeder_utilization = (
            feeder_tph / FEEDER_DESIGN_TPH * 100.0
        )

    if dmc_utilization is None and dmc_tph is not None:
        dmc_utilization = (
            dmc_tph / DMC_DESIGN_TPH * 100.0
        )

    return {
        **values,
        "clean_coal_tons": clean_coal,
        "feed_tons_final": feed,
        "recovery": recovery,
        "reject_ratio": reject_ratio,
        "clean_coal_share": clean_coal_share,
        "peas_share": peas_share,
        "nuts_share": nuts_share,
        "feeder_tph": feeder_tph,
        "dmc_tph": dmc_tph,
        "feeder_availability_final": feeder_availability,
        "dmc_availability_final": dmc_availability,
        "feeder_utilization_final": feeder_utilization,
        "dmc_utilization_final": dmc_utilization,
        "clean_coal_derived": clean_coal_derived,
        "feed_derived": derived_feed,
    }


def quality_data_status(
    df: pd.DataFrame,
    field_map: dict[str, Optional[str]],
) -> tuple[str, list[str]]:
    """
    Determine quality-data availability from actual database fields.

    Returns:
        ("DATA AVAILABLE", populated fields) when at least one configured
        quality field exists and contains numeric data.
        ("FIELDS AVAILABLE - NO VALID DATA", fields) when quality columns
        exist but contain no numeric values.
        ("NOT CONFIGURED", []) when no recognized quality field exists.

    This function never creates or assumes a quality value.
    """
    quality_keys = [
        "feed_ash",
        "feed_sulphur",
        "peas_ash",
        "peas_sulphur",
        "nuts_ash",
        "nuts_sulphur",
        "clean_coal_ash",
        "clean_coal_sulphur",
    ]

    existing_fields: list[str] = []
    populated_fields: list[str] = []

    for key in quality_keys:
        column = field_map.get(key)
        if column:
            existing_fields.append(column)
            values = pd.to_numeric(df[column], errors="coerce")
            if values.notna().sum() > 0:
                populated_fields.append(column)

    if populated_fields:
        return "DATA AVAILABLE", populated_fields

    if existing_fields:
        return "FIELDS AVAILABLE - NO VALID DATA", existing_fields

    return "NOT CONFIGURED", []


def fmt_tons(value: Optional[float]) -> str:
    if value is None:
        return "Not available"
    return f"{value:,.1f} t"


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "Not available"
    return f"{value:.1f}%"


def fmt_hours(value: Optional[float]) -> str:
    if value is None:
        return "Not available"
    return f"{value:.2f} h"


def fmt_tph(value: Optional[float]) -> str:
    if value is None:
        return "Not available"
    return f"{value:.1f} tph"


def status_for(
    value: Optional[float],
    reference: float,
    higher_is_better: bool = True,
) -> str:

    if value is None:
        return "NOT CONFIGURED"

    if higher_is_better:
        if value >= reference:
            return "GOOD"
        if value >= reference * 0.90:
            return "WATCH"
        return "ATTENTION"

    if value <= reference:
        return "GOOD"
    if value <= reference * 1.10:
        return "WATCH"
    return "ATTENTION"


def status_class(status: str) -> str:
    if status == "GOOD":
        return "good"
    if status == "WATCH":
        return "watch"
    return "attention"


def select_period(
    df: pd.DataFrame,
    view: str,
    selected_day,
) -> tuple[pd.DataFrame, str]:

    if view == "Day":
        period = df[
            df["production_day"] == selected_day
        ].copy()

        label = pd.Timestamp(selected_day).strftime(
            "%d %b %Y"
        )

        return period, label

    if view == "Month":
        period = df[
            (
                df["production_date"].dt.year
                == selected_day.year
            )
            &
            (
                df["production_date"].dt.month
                == selected_day.month
            )
        ].copy()

        label = pd.Timestamp(selected_day).strftime(
            "%B %Y"
        )

        return period, label

    period = df[
        df["production_date"].dt.year
        == selected_day.year
    ].copy()

    label = str(selected_day.year)

    return period, label


# ============================================================
# SIDEBAR
# ============================================================

# Authentication, navigation and signed-in user information are rendered
# centrally by auth.py through show_user_sidebar(). This page does not create
# a second sidebar.

# ============================================================
# LOAD DATA
# ============================================================

try:
    df = load_production_data()
except Exception as exc:
    st.title("🧭 CHPP Management Intelligence")
    st.error(
        f"Unable to load production data from Supabase: {exc}"
    )
    st.stop()


# ============================================================
# EMPTY DATA STATE
# ============================================================

if df.empty:
    st.title("🧭 CHPP Management Intelligence")
    st.info(
        "No production records are currently available. "
        "Enter production data from the Production Input module."
    )
    st.stop()


if "production_date" not in df.columns:
    st.error(
        "The production table does not contain a recognizable "
        "production_date field."
    )
    st.stop()


df = df[
    df["production_date"].notna()
].copy()

if df.empty:
    st.warning(
        "No valid production dates are available."
    )
    st.stop()


df["production_day"] = df["production_date"].dt.date

available_days = sorted(
    df["production_day"].unique(),
    reverse=True,
)

available_dates = sorted(
    {
        pd.Timestamp(day)
        for day in available_days
    },
    reverse=True,
)

field_map = build_field_map(df)


# ============================================================
# HEADER
# ============================================================

top_left, top_right = st.columns(
    [4, 1],
    vertical_alignment="center",
)

with top_left:
    st.markdown(
        '<div class="main-title">🧠 CHPP Management Intelligence</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="chpp-trademark">Designed & Developed by Levy Mukopeka</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="subtitle">'
        'Management decision support • production performance • '
        'equipment health • operational attention areas'
        '</div>',
        unsafe_allow_html=True,
    )

with top_right:
    st.markdown(
        '<div class="status">● SYSTEM ONLINE</div>',
        unsafe_allow_html=True,
    )

st.caption(
    f"Management view • Signed in as "
    f"{user.get('full_name') or user.get('username')} "
    f"({user.get('role')})"
)


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
)

date_col, refresh_col = st.columns(
    [5, 1],
    vertical_alignment="bottom",
)

with date_col:
    # Calendar selector: users are no longer restricted to dates already
    # present in the database. A date with no production record is handled
    # explicitly below.
    latest_available_date = max(available_dates).date()

    selected_day = st.date_input(
        "Production Date",
        value=latest_available_date,
        min_value=min(available_dates).date(),
        max_value=pd.Timestamp.today().date(),
        format="DD/MM/YYYY",
    )

with refresh_col:
    if st.button(
        "↻ Refresh",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.rerun()


period_df, period_label = select_period(
    df,
    view,
    selected_day,
)

st.caption(
    f"Showing management intelligence for **{period_label}** "
    f"({len(period_df):,} production record(s))."
)

if period_df.empty:
    st.warning(
        "No production records exist for the selected period."
    )
    st.stop()


# ============================================================
# CALCULATIONS
# ============================================================

period_values = aggregate_period(
    period_df,
    field_map,
)

m = derive_metrics(period_values)


# ============================================================
# EXECUTIVE MANAGEMENT SUMMARY
# ============================================================

st.markdown(
    '<div class="section-title">EXECUTIVE MANAGEMENT SUMMARY</div>',
    unsafe_allow_html=True,
)

summary_cols = st.columns(5)

summary_items = [
    (
        "Clean Coal",
        fmt_tons(m["clean_coal_tons"]),
        "Peas + Nuts where required",
    ),
    (
        "Plant Recovery",
        fmt_pct(m["recovery"]),
        "Reference: 66.7%",
    ),
    (
        "DMC Throughput",
        fmt_tph(m["dmc_tph"]),
        f"Design: {DMC_DESIGN_TPH:.0f} tph",
    ),
    (
        "DMC Availability",
        fmt_pct(m["dmc_availability_final"]),
        f"Reference: {REFERENCE_AVAILABILITY_PCT:.0f}%",
    ),
    (
        "DMC OEE",
        fmt_pct(m["dmc_oee"]),
        f"Reference: {REFERENCE_DMC_OEE_PCT:.0f}%",
    ),
]

for col, item in zip(summary_cols, summary_items):
    with col:
        label, value, note = item
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


# ============================================================
# MANAGEMENT DECISION STATUS
# ============================================================

st.markdown(
    '<div class="section-title">MANAGEMENT DECISION STATUS</div>',
    unsafe_allow_html=True,
)

recovery_status = status_for(
    m["recovery"],
    REFERENCE_RECOVERY_PCT,
)

throughput_pct = None

if m["dmc_tph"] is not None:
    throughput_pct = (
        m["dmc_tph"] / DMC_DESIGN_TPH * 100.0
    )

throughput_status = status_for(
    throughput_pct,
    REFERENCE_THROUGHPUT_PCT,
)

availability_status = status_for(
    m["dmc_availability_final"],
    REFERENCE_AVAILABILITY_PCT,
)

oee_status = status_for(
    m["dmc_oee"],
    REFERENCE_DMC_OEE_PCT,
)


decision_cols = st.columns(4)

decision_data = [
    (
        "Production Throughput",
        throughput_status,
        (
            f"DMC is operating at {fmt_tph(m['dmc_tph'])}, "
            f"which is {fmt_pct(throughput_pct)} of the "
            f"{DMC_DESIGN_TPH:.0f} tph design reference."
            if throughput_pct is not None
            else
            "DMC throughput is not available from the selected data."
        ),
    ),
    (
        "Plant Recovery",
        recovery_status,
        (
            f"Clean-coal recovery is {fmt_pct(m['recovery'])} "
            f"against the {REFERENCE_RECOVERY_PCT:.1f}% reference."
            if m["recovery"] is not None
            else
            "Recovery cannot be evaluated because the required "
            "production streams are not available."
        ),
    ),
    (
        "DMC Availability",
        availability_status,
        (
            f"DMC availability is "
            f"{fmt_pct(m['dmc_availability_final'])}."
            if m["dmc_availability_final"] is not None
            else
            "DMC availability is not configured for the selected period."
        ),
    ),
    (
        "DMC OEE",
        oee_status,
        (
            f"DMC OEE is {fmt_pct(m['dmc_oee'])} against the "
            f"{REFERENCE_DMC_OEE_PCT:.0f}% reference."
            if m["dmc_oee"] is not None
            else
            "DMC OEE is not configured from the available database fields."
        ),
    ),
]

for col, item in zip(decision_cols, decision_data):

    with col:

        title, status, text = item

        cls = status_class(status)

        st.markdown(
            f"""
            <div class="decision-card">
                <div class="decision-title {cls}">
                    {title} — {status}
                </div>
                <div class="decision-text">
                    {text}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# KEY MANAGEMENT ATTENTION AREAS
# ============================================================

st.markdown(
    '<div class="section-title">KEY MANAGEMENT ATTENTION AREAS</div>',
    unsafe_allow_html=True,
)

attention_items: list[tuple[str, str, str]] = []

if throughput_status == "ATTENTION":
    attention_items.append(
        (
            "Throughput",
            "attention",
            f"DMC throughput is below the {REFERENCE_THROUGHPUT_PCT:.0f}% "
            f"management reference of design capacity.",
        )
    )
elif throughput_status == "WATCH":
    attention_items.append(
        (
            "Throughput",
            "watch",
            f"DMC throughput is close to the management reference "
            f"but should be monitored.",
        )
    )

if recovery_status == "ATTENTION":
    attention_items.append(
        (
            "Recovery",
            "attention",
            f"Plant recovery is below the {REFERENCE_RECOVERY_PCT:.1f}% "
            f"reference.",
        )
    )
elif recovery_status == "WATCH":
    attention_items.append(
        (
            "Recovery",
            "watch",
            "Plant recovery is close to the management reference.",
        )
    )

if availability_status == "ATTENTION":
    attention_items.append(
        (
            "Availability",
            "attention",
            f"DMC availability is below the "
            f"{REFERENCE_AVAILABILITY_PCT:.0f}% reference.",
        )
    )
elif availability_status == "WATCH":
    attention_items.append(
        (
            "Availability",
            "watch",
            "DMC availability is approaching the management threshold.",
        )
    )

if oee_status == "ATTENTION":
    attention_items.append(
        (
            "OEE",
            "attention",
            f"DMC OEE is below the {REFERENCE_DMC_OEE_PCT:.0f}% reference.",
        )
    )
elif oee_status == "WATCH":
    attention_items.append(
        (
            "OEE",
            "watch",
            "DMC OEE is close to the management reference.",
        )
    )

reject_ratio = m["reject_ratio"]

if reject_ratio is not None and reject_ratio > 33.3:
    attention_items.append(
        (
            "Rejects",
            "attention",
            f"Reject ratio is {reject_ratio:.1f}% of DMC feed. "
            "Review the material balance and operating conditions.",
        )
    )

if not attention_items:
    st.success(
        "No major management attention flags were identified "
        "from the available production and equipment data."
    )
else:
    for title, level, text in attention_items:
        if level == "attention":
            st.markdown(
                f"""
                <div class="danger-box">
                    <strong>{title}</strong> — {text}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="warning-box">
                    <strong>{title}</strong> — {text}
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# PRODUCTION POSITION
# ============================================================

st.markdown(
    '<div class="section-title">PRODUCTION POSITION</div>',
    unsafe_allow_html=True,
)

prod_cols = st.columns(4)

production_metrics = [
    (
        "DMC Feed",
        fmt_tons(m["feed_tons_final"]),
        "Material processed",
    ),
    (
        "Peas",
        fmt_tons(m["peas_tons"]),
        (
            f"{fmt_pct(m['peas_share'])} of clean coal"
            if m["peas_share"] is not None
            else "Share not available"
        ),
    ),
    (
        "Nuts",
        fmt_tons(m["nuts_tons"]),
        (
            f"{fmt_pct(m['nuts_share'])} of clean coal"
            if m["nuts_share"] is not None
            else "Share not available"
        ),
    ),
    (
        "Rejects",
        fmt_tons(m["rejects_tons"]),
        (
            f"{fmt_pct(m['reject_ratio'])} of DMC feed"
            if m["reject_ratio"] is not None
            else "Ratio not available"
        ),
    ),
]

for col, item in zip(prod_cols, production_metrics):
    with col:
        label, value, note = item
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


# ============================================================
# MATERIAL BALANCE / CLEAN COAL MIX
# ============================================================

st.markdown(
    '<div class="section-title">MATERIAL BALANCE & CLEAN-COAL MIX</div>',
    unsafe_allow_html=True,
)

left, right = st.columns(2)

with left:

    st.subheader("Material Balance")

    balance_rows = []

    if m["feed_tons_final"] is not None:
        balance_rows.append(
            ("DMC Feed", m["feed_tons_final"])
        )

    if m["clean_coal_tons"] is not None:
        balance_rows.append(
            ("Clean Coal", m["clean_coal_tons"])
        )

    if m["rejects_tons"] is not None:
        balance_rows.append(
            ("Rejects", m["rejects_tons"])
        )

    if m["fines_tons"] is not None:
        balance_rows.append(
            ("Fines / Ultrafines", m["fines_tons"])
        )

    if balance_rows:

        balance_df = pd.DataFrame(
            balance_rows,
            columns=["Stream", "Tonnes"],
        )

        if px is not None:
            fig = px.bar(
                balance_df,
                x="Stream",
                y="Tonnes",
                text="Tonnes",
            )

            fig.update_traces(
                texttemplate="%{text:.1f}",
                textposition="outside",
            )

            fig.update_layout(
                height=360,
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20,
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#d8e1ec"),
                xaxis=dict(
                    title=None,
                    gridcolor="#263548",
                ),
                yaxis=dict(
                    title="Tonnes",
                    gridcolor="#263548",
                ),
                showlegend=False,
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

        else:
            st.dataframe(
                balance_df,
                use_container_width=True,
                hide_index=True,
            )

    else:
        st.info("Material balance data is not available.")


with right:

    st.subheader("Clean Coal Composition")

    composition_rows = []

    if m["peas_tons"] is not None:
        composition_rows.append(
            ("Peas", m["peas_tons"])
        )

    if m["nuts_tons"] is not None:
        composition_rows.append(
            ("Nuts", m["nuts_tons"])
        )

    if composition_rows:

        composition_df = pd.DataFrame(
            composition_rows,
            columns=["Stream", "Tonnes"],
        )

        if px is not None:
            fig = px.pie(
                composition_df,
                names="Stream",
                values="Tonnes",
                hole=0.45,
            )

            fig.update_layout(
                height=360,
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20,
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#d8e1ec"),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.10,
                    xanchor="center",
                    x=0.5,
                ),
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

        else:
            st.dataframe(
                composition_df,
                use_container_width=True,
                hide_index=True,
            )

    else:
        st.info(
            "Peas and Nuts data is not available for the selected period."
        )


# ============================================================
# EQUIPMENT MANAGEMENT VIEW
# ============================================================

st.markdown(
    '<div class="section-title">EQUIPMENT MANAGEMENT VIEW</div>',
    unsafe_allow_html=True,
)

equipment_cols = st.columns(4)

equipment_metrics = [
    (
        "Feeder Availability",
        fmt_pct(m["feeder_availability_final"]),
        f"Reference: {REFERENCE_AVAILABILITY_PCT:.0f}%",
    ),
    (
        "Feeder OEE",
        fmt_pct(m["feeder_oee"]),
        "From existing production KPI data",
    ),
    (
        "DMC Availability",
        fmt_pct(m["dmc_availability_final"]),
        f"Reference: {REFERENCE_AVAILABILITY_PCT:.0f}%",
    ),
    (
        "DMC OEE",
        fmt_pct(m["dmc_oee"]),
        f"Reference: {REFERENCE_DMC_OEE_PCT:.0f}%",
    ),
]

for col, item in zip(equipment_cols, equipment_metrics):
    with col:
        label, value, note = item
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


# ============================================================
# EQUIPMENT COMPARISON
# ============================================================

comparison_rows = []

comparison_rows.append(
    {
        "Parameter": "Throughput",
        "Feeder": fmt_tph(m["feeder_tph"]),
        "DMC": fmt_tph(m["dmc_tph"]),
    }
)

comparison_rows.append(
    {
        "Parameter": "Availability",
        "Feeder": fmt_pct(m["feeder_availability_final"]),
        "DMC": fmt_pct(m["dmc_availability_final"]),
    }
)

comparison_rows.append(
    {
        "Parameter": "Utilisation",
        "Feeder": fmt_pct(m["feeder_utilization_final"]),
        "DMC": fmt_pct(m["dmc_utilization_final"]),
    }
)

comparison_rows.append(
    {
        "Parameter": "OEE",
        "Feeder": fmt_pct(m["feeder_oee"]),
        "DMC": fmt_pct(m["dmc_oee"]),
    }
)

comparison_df = pd.DataFrame(comparison_rows)

with st.expander(
    "View equipment performance comparison",
    expanded=False,
):
    st.dataframe(
        comparison_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# OPERATIONAL TIME
# ============================================================

st.markdown(
    '<div class="section-title">OPERATIONAL TIME</div>',
    unsafe_allow_html=True,
)

time_cols = st.columns(4)

time_metrics = [
    (
        "Planned Hours",
        fmt_hours(m["planned_hours"]),
    ),
    (
        "Feeder Running",
        fmt_hours(m["feeder_running_hours"]),
    ),
    (
        "DMC Running",
        fmt_hours(m["dmc_running_hours"]),
    ),
    (
        "DMC Downtime",
        fmt_hours(m["dmc_downtime_hours"]),
    ),
]

for col, item in zip(time_cols, time_metrics):
    with col:
        label, value = item
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# PERFORMANCE TREND
# ============================================================

st.markdown(
    '<div class="section-title">PERFORMANCE TREND</div>',
    unsafe_allow_html=True,
)

trend_df = df.copy()

trend_df["production_day"] = (
    trend_df["production_date"].dt.date
)

trend_rows = []

for day, group in trend_df.groupby("production_day"):

    values = aggregate_period(
        group,
        field_map,
    )

    metrics = derive_metrics(values)

    trend_rows.append(
        {
            "Date": pd.Timestamp(day),
            "Clean Coal": metrics["clean_coal_tons"],
            "DMC Throughput": metrics["dmc_tph"],
            "Recovery": metrics["recovery"],
            "DMC Availability": metrics["dmc_availability_final"],
            "DMC OEE": metrics["dmc_oee"],
        }
    )

trend = pd.DataFrame(trend_rows).sort_values(
    "Date"
)

if not trend.empty:

    # Show a manageable recent window for the management page.
    if view == "Day":
        display_trend = trend.tail(14)
    elif view == "Month":
        display_trend = trend.tail(31)
    else:
        display_trend = trend.tail(90)

    if px is not None:

        chart_cols = st.columns(2)

        with chart_cols[0]:

            st.subheader("Clean Coal Production Trend")

            clean_trend = display_trend[
                [
                    "Date",
                    "Clean Coal",
                ]
            ].dropna()

            if not clean_trend.empty:

                fig = px.line(
                    clean_trend,
                    x="Date",
                    y="Clean Coal",
                    markers=True,
                )

                fig.update_layout(
                    height=330,
                    margin=dict(
                        l=20,
                        r=20,
                        t=20,
                        b=20,
                    ),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#d8e1ec"),
                    xaxis=dict(
                        title=None,
                        gridcolor="#263548",
                    ),
                    yaxis=dict(
                        title="Tonnes",
                        gridcolor="#263548",
                    ),
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                )

            else:
                st.info(
                    "Clean-coal trend data is not available."
                )

        with chart_cols[1]:

            st.subheader("Recovery Trend")

            recovery_trend = display_trend[
                [
                    "Date",
                    "Recovery",
                ]
            ].dropna()

            if not recovery_trend.empty:

                fig = px.line(
                    recovery_trend,
                    x="Date",
                    y="Recovery",
                    markers=True,
                )

                fig.add_hline(
                    y=REFERENCE_RECOVERY_PCT,
                    line_dash="dash",
                    annotation_text=(
                        f"Reference {REFERENCE_RECOVERY_PCT:.1f}%"
                    ),
                )

                fig.update_layout(
                    height=330,
                    margin=dict(
                        l=20,
                        r=20,
                        t=20,
                        b=20,
                    ),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#d8e1ec"),
                    xaxis=dict(
                        title=None,
                        gridcolor="#263548",
                    ),
                    yaxis=dict(
                        title="Recovery (%)",
                        gridcolor="#263548",
                    ),
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                )

            else:
                st.info(
                    "Recovery trend data is not available."
                )

    else:
        st.dataframe(
            display_trend,
            use_container_width=True,
            hide_index=True,
        )

else:
    st.info(
        "Not enough historical records are available to display a trend."
    )


# ============================================================
# DATA INTEGRITY / QUALITY CONFIGURATION
# ============================================================

st.markdown(
    '<div class="section-title">DATA & INTELLIGENCE STATUS</div>',
    unsafe_allow_html=True,
)

status_left, status_right = st.columns(2)

with status_left:

    st.subheader("Available Management Inputs")

    status_rows = [
        (
            "Production Date",
            field_map["production_date"],
        ),
        (
            "DMC Feed",
            field_map["dmc_feed_tons"],
        ),
        (
            "Peas",
            field_map["peas_tons"],
        ),
        (
            "Nuts",
            field_map["nuts_tons"],
        ),
        (
            "Rejects",
            field_map["rejects_tons"],
        ),
        (
            "DMC Running Hours",
            field_map["dmc_running_hours"],
        ),
        (
            "DMC Availability",
            field_map["dmc_availability"],
        ),
        (
            "DMC OEE",
            field_map["dmc_oee"],
        ),
    ]

    status_table = pd.DataFrame(
        [
            {
                "Parameter": name,
                "Database Field": field or "Not found",
                "Status": (
                    "Available"
                    if field
                    else "Not configured"
                ),
            }
            for name, field in status_rows
        ]
    )

    st.dataframe(
        status_table,
        use_container_width=True,
        hide_index=True,
    )

with status_right:

    st.subheader("Quality Intelligence Status")

    quality_status, quality_fields = quality_data_status(
        period_df,
        field_map,
    )

    if quality_status == "DATA AVAILABLE":
        st.markdown(
            f"""
            <div class="info-box">
                <strong>Quality Intelligence — DATA AVAILABLE</strong>
                <br><br>
                Actual quality data was found for the selected reporting
                period. The detected database field(s) are:
                <strong>{", ".join(quality_fields)}</strong>.
                <br><br>
                This module does not invent quality values or use them in
                OEE/management scoring. A dedicated Quality Intelligence
                module can use the actual measurements against configured
                specifications.
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif quality_status == "FIELDS AVAILABLE - NO VALID DATA":
        st.markdown(
            f"""
            <div class="warning-box">
                <strong>Quality Intelligence — FIELDS AVAILABLE, NO VALID DATA</strong>
                <br><br>
                Quality column(s) exist in the database, but no numeric
                quality measurements are available for the selected period:
                <strong>{", ".join(quality_fields)}</strong>.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="info-box">
                <strong>Quality Intelligence — NOT CONFIGURED</strong>
                <br><br>
                No recognized coal-quality fields are currently available
                in the production database for this management view.
                Therefore no quality score, quality factor,
                quality-adjusted OEE, or quality-based management decision
                is invented here.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(
        "Quality status is determined from actual database fields and data; "
        "it is not hard-coded."
    )


# ============================================================
# MANAGEMENT ACTIONS
# ============================================================

st.markdown(
    '<div class="section-title">MANAGEMENT ACTIONS</div>',
    unsafe_allow_html=True,
)

actions: list[tuple[str, str]] = []

if throughput_status in {"ATTENTION", "WATCH"}:
    actions.append(
        (
            "Throughput",
            "Review DMC running hours and actual throughput against "
            "the design reference.",
        )
    )

if availability_status in {"ATTENTION", "WATCH"}:
    actions.append(
        (
            "Availability",
            "Review DMC downtime and the causes of lost operating time.",
        )
    )

if oee_status in {"ATTENTION", "WATCH"}:
    actions.append(
        (
            "OEE",
            "Review the OEE components already recorded in the production "
            "KPI data and identify the dominant loss.",
        )
    )

if recovery_status in {"ATTENTION", "WATCH"}:
    actions.append(
        (
            "Recovery",
            "Review clean-coal production versus DMC feed and investigate "
            "the material-balance position.",
        )
    )

if reject_ratio is not None and reject_ratio > 33.3:
    actions.append(
        (
            "Rejects",
            "Review reject production and confirm the material balance "
            "against DMC feed.",
        )
    )

if not actions:
    actions.append(
        (
            "Routine Monitoring",
            "Continue monitoring production, equipment performance and "
            "material balance using the selected reporting period.",
        )
    )

action_df = pd.DataFrame(
    actions,
    columns=["Management Area", "Recommended Review"],
)

# The action list is generated from the selected period's live KPI values.
# The wording is fixed, but the rows shown are data-driven.
st.dataframe(
    action_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# DATA DERIVATION NOTES
# ============================================================

notes = []

if m["clean_coal_derived"]:
    notes.append(
        "Clean Coal is derived from Peas + Nuts because no direct "
        "clean-coal field was available."
    )

if m["feed_derived"]:
    notes.append(
        "DMC Feed is derived from the available material streams because "
        "a direct DMC feed field was not available."
    )

if m["dmc_tph"] is not None:
    notes.append(
        "DMC throughput is calculated as DMC feed tonnes divided by "
        "DMC running hours."
    )

if m["feeder_tph"] is not None:
    notes.append(
        "Feeder throughput is calculated as feeder tonnes divided by "
        "feeder running hours."
    )

notes.append(
    "No coal-quality values are invented or used in management scoring."
)

if notes:

    st.markdown(
        '<div class="section-title">CALCULATION NOTES</div>',
        unsafe_allow_html=True,
    )

    for note in notes:
        st.markdown(
            f"- {note}"
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "CHPP-PIS • Management Intelligence • "
    "Uses existing production and equipment records • "
    "No quality values are invented"
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
