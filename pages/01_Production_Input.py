import os
from datetime import date

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

from auth import require_login, show_user_sidebar

st.set_page_config(
    page_title="Production Input | CHPP-PIS",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# AUTHENTICATION / AUTHORIZATION
# ============================================================

user = require_login(
    allowed_roles=[
        "Administrator",
        "Management",
        "Supervisor",
        "Operator",
    ]
)

show_user_sidebar()

USER_ROLE = user.get("role")

# Management has read-only access.
READ_ONLY = USER_ROLE == "Management"

# Administrator, Supervisor and Operator can enter/update data.
CAN_EDIT = USER_ROLE in [
    "Administrator",
    "Supervisor",
    "Operator",
]


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Production Input | CHPP-PIS",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# ============================================================
# SUPABASE CONNECTION
# ============================================================

@st.cache_resource
def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "Supabase configuration is missing. "
            "Please check SUPABASE_URL and SUPABASE_KEY in the .env file."
        )

    return create_client(SUPABASE_URL, SUPABASE_KEY)


try:
    supabase = get_supabase()
except Exception as e:
    st.error(f"Unable to connect to Supabase: {e}")
    st.stop()


# ============================================================
# CUSTOM STYLING
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1200px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .page-title {
        font-size: 2rem;
        font-weight: 750;
        margin-bottom: 0.15rem;
    }
        .developer-credit {
        color: #60a5fa;
        font-size: 0.78rem;
        font-weight: 500;
        margin-top: 0.15rem;
        margin-bottom: 1.2rem;
        letter-spacing: 0.02em;
    }

    .page-subtitle {
        color: #9ca3af;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #60a5fa;
        margin-top: 1.6rem;
        margin-bottom: 0.8rem;
    }

    .input-banner {
        background: #122238;
        border: 1px solid #234566;
        border-radius: 10px;
        padding: 0.9rem 1rem;
        margin-bottom: 1.4rem;
        color: #dbeafe;
    }

    .existing-banner {
        background: #19334d;
        border: 1px solid #28577d;
        border-radius: 10px;
        padding: 0.85rem 1rem;
        margin: 0.8rem 0 1.2rem 0;
        color: #dbeafe;
    }

    .summary-card {
        background: #101923;
        border: 1px solid #26384a;
        border-radius: 10px;
        padding: 0.9rem 1rem;
        min-height: 92px;
    }

    .summary-label {
        color: #8fa7bf;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .summary-value {
        color: #f8fafc;
        font-size: 1.55rem;
        font-weight: 700;
        margin-top: 0.25rem;
    }

    .footer {
        margin-top: 3rem;
        padding-top: 1.25rem;
        border-top: 1px solid #30343b;
        text-align: center;
    }

    .footer-main {
        font-weight: 600;
        font-size: 0.9rem;
    }

    .footer-sub {
        color: #9ca3af;
        font-size: 0.82rem;
        font-style: italic;
        margin-top: 0.25rem;
    }

    footer {
        visibility: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# PAGE HEADER
# ============================================================

st.markdown(
    '<div class="page-title">📝 Production Input</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="developer-credit">Designed & Developed by Levy Mukopeka</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="page-subtitle">'
    "Daily CHPP production and operating data entry"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# INFORMATION BANNER
# ============================================================

st.markdown(
    """
    <div class="input-banner">
        Enter the daily CHPP production figures and operating hours.
        Existing records can be selected by date and updated.
        Production KPIs are calculated automatically from the saved record.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# RECORD INFORMATION
# ============================================================

st.markdown(
    '<div class="section-title">Record Information</div>',
    unsafe_allow_html=True,
)

date_col, status_col = st.columns([2.5, 1])

with date_col:
    production_date = st.date_input(
        "Production Date",
        value=date.today(),
        format="DD/MM/YYYY",
        help="Select the production date you want to enter or update.",
    )

production_date_str = production_date.isoformat()


# ============================================================
# CHECK FOR EXISTING RECORD
# ============================================================

existing_record = None

try:
    existing_response = (
        supabase
        .table("chpp_production_records")
        .select("*")
        .eq("production_date", production_date_str)
        .execute()
    )

    if existing_response.data:
        existing_record = existing_response.data[0]

except Exception as e:
    st.error(f"Unable to check existing production record: {e}")
    st.stop()


with status_col:
    st.markdown("**Record Status**")
    if existing_record:
        st.success("Existing record")
    else:
        st.info("New record")


if existing_record:
    st.markdown(
        """
        <div class="existing-banner">
            <strong>Existing record found.</strong>
            The values below have been loaded from Supabase.
            Change any value you need and select <strong>Update Production Record</strong>.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# DEFAULT VALUE HELPER
# ============================================================

def existing_value(column_name, default=0.0):
    if existing_record:
        value = existing_record.get(column_name)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
    return default


# ============================================================
# PRODUCTION INPUTS
# ============================================================

st.markdown(
    '<div class="section-title">Production Inputs</div>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)

with col1:
    feed_to_dmc_tons = st.number_input(
        "Feed to DMC (t)",
        min_value=0.0,
        value=existing_value("feed_to_dmc_tons"),
        step=10.0,
        format="%.2f",
        help="Total tonnes fed to the Dense Medium Cyclone.",
    )

with col2:
    peas_tons = st.number_input(
        "Peas (t)",
        min_value=0.0,
        value=existing_value("peas_tons"),
        step=10.0,
        format="%.2f",
        help="Daily washed peas production.",
    )

with col3:
    nuts_tons = st.number_input(
        "Nuts (t)",
        min_value=0.0,
        value=existing_value("nuts_tons"),
        step=10.0,
        format="%.2f",
        help="Daily washed nuts production.",
    )

col1, col2, col3 = st.columns(3)

with col1:
    rejects_tons = st.number_input(
        "Rejects (t)",
        min_value=0.0,
        value=existing_value("rejects_tons"),
        step=10.0,
        format="%.2f",
        help="Daily rejects production.",
    )

with col2:
    fines_belt_tons = st.number_input(
        "Fines Belt (t)",
        min_value=0.0,
        value=existing_value("fines_belt_tons"),
        step=10.0,
        format="%.2f",
        help="Daily fines belt production.",
    )

with col3:
    feeder_tons = st.number_input(
        "Feeder (t)",
        min_value=0.0,
        value=existing_value("feeder_tons"),
        step=10.0,
        format="%.2f",
        help="Total tonnes recorded through the feeder.",
    )


# ============================================================
# LIVE PRODUCTION SUMMARY
# ============================================================

clean_coal_tons = peas_tons + nuts_tons
total_stream_tons = clean_coal_tons + rejects_tons + fines_belt_tons

st.markdown(
    '<div class="section-title">Production Summary</div>',
    unsafe_allow_html=True,
)

s1, s2, s3 = st.columns(3)

with s1:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Clean Coal</div>
            <div class="summary-value">{clean_coal_tons:,.2f} t</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with s2:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Peas + Nuts</div>
            <div class="summary-value">{clean_coal_tons:,.2f} t</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with s3:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">Total Recorded Streams</div>
            <div class="summary-value">{total_stream_tons:,.2f} t</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# OPERATING HOURS
# ============================================================

st.markdown(
    '<div class="section-title">Operating Hours</div>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)

with col1:
    planned_hours = st.number_input(
        "Planned Hours",
        min_value=0.0,
        max_value=24.0,
        value=existing_value("planned_hours"),
        step=0.5,
        format="%.2f",
        help="Planned plant operating hours.",
    )

with col2:
    feeder_running_hours = st.number_input(
        "Feeder Running Hours",
        min_value=0.0,
        max_value=24.0,
        value=existing_value("feeder_running_hours"),
        step=0.5,
        format="%.2f",
        help="Actual feeder running time.",
    )

with col3:
    dmc_running_hours = st.number_input(
        "DMC Running Hours",
        min_value=0.0,
        max_value=24.0,
        value=existing_value("dmc_running_hours"),
        step=0.5,
        format="%.2f",
        help="Actual DMC running time.",
    )


# ============================================================
# VALIDATION
# ============================================================

validation_errors = []
validation_warnings = []

if feeder_running_hours > planned_hours:
    validation_errors.append(
        "Feeder Running Hours cannot exceed Planned Hours."
    )

if dmc_running_hours > planned_hours:
    validation_errors.append(
        "DMC Running Hours cannot exceed Planned Hours."
    )

if feeder_tons > 0 and feed_to_dmc_tons > feeder_tons:
    validation_errors.append(
        "Feed to DMC Tons cannot be greater than Feeder Tons. "
        "Please verify the two values."
    )

if feed_to_dmc_tons > 0 and total_stream_tons > feed_to_dmc_tons:
    validation_warnings.append(
        "The combined production streams are greater than Feed to DMC. "
        "Please verify the material balance."
    )

if planned_hours == 0 and (
    feeder_running_hours > 0 or dmc_running_hours > 0
):
    validation_errors.append(
        "Running hours cannot be entered when Planned Hours is zero."
    )


if validation_errors:
    for error in validation_errors:
        st.error(error)

if validation_warnings:
    for warning in validation_warnings:
        st.warning(warning)


# ============================================================
# SAVE / UPDATE
# ============================================================

st.markdown("")

button_label = (
    "Update Production Record"
    if existing_record
    else "Save Production Record"
)

submitted = st.button(
    button_label,
    type="primary",
    use_container_width=True,
)


# ============================================================
# SAVE / UPDATE RECORD
# ============================================================

if submitted:

    if validation_errors:
        st.error(
            "Please correct the validation errors before saving."
        )
        st.stop()

    record = {
        "production_date": production_date_str,
        "feed_to_dmc_tons": feed_to_dmc_tons,
        "peas_tons": peas_tons,
        "nuts_tons": nuts_tons,
        "rejects_tons": rejects_tons,
        "fines_belt_tons": fines_belt_tons,
        "feeder_tons": feeder_tons,
        "planned_hours": planned_hours,
        "feeder_running_hours": feeder_running_hours,
        "dmc_running_hours": dmc_running_hours,
    }

    try:

        if existing_record:
            response = (
                supabase
                .table("chpp_production_records")
                .update(record)
                .eq("production_date", production_date_str)
                .execute()
            )

            if response.data:
                st.success(
                    f"Production record for {production_date.strftime('%d/%m/%Y')} "
                    "updated successfully."
                )
            else:
                st.error("The production record could not be updated.")

        else:
            response = (
                supabase
                .table("chpp_production_records")
                .insert(record)
                .execute()
            )

            if response.data:
                st.success(
                    f"Production record for {production_date.strftime('%d/%m/%Y')} "
                    "saved successfully."
                )
            else:
                st.error("The production record could not be saved.")

        if response.data:
            st.info(
                "Production KPIs will use this saved record automatically."
            )

    except Exception as e:
        st.error(f"Unable to save production record: {e}")


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        <div class="footer-main">CHPP-PIS • Production Intelligence System</div>
        <div class="footer-sub">
            Daily production input • Supabase-connected • KPI-ready
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
