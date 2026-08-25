import streamlit as st
from datetime import date

from auth import require_login, show_user_sidebar

# ============================================================
# CHPP-PIS
# HOME / EXECUTIVE LANDING PAGE
# ============================================================

st.set_page_config(
    page_title="CHPP-PIS",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# AUTHENTICATION
# ============================================================

# Require username/password login before accessing CHPP-PIS
user = require_login()

# Display signed-in user and logout control
show_user_sidebar()

# ============================================================
# PAGE STYLING
# ============================================================

st.markdown(
    """
    <style>

    /* Main page spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* Compact main heading */
    .chpp-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.15rem;
    }

    .chpp-subtitle {
        font-size: 0.95rem;
        color: #9ca3af;
        margin-bottom: 1.5rem;
    }

    /* Footer */
    .footer-text {
        text-align: center;
        color: #9ca3af;
        font-size: 0.85rem;
        padding-top: 1rem;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="chpp-title">🏭 CHPP Production Intelligence System</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="chpp-subtitle">Daily Plant Performance Overview</div>',
    unsafe_allow_html=True
)

# ============================================================
# DATE + SYSTEM STATUS
# ============================================================

date_col, status_col = st.columns([1, 3])

with date_col:

    production_date = st.date_input(
        "Production Date",
        value=date.today(),
        format="DD/MM/YYYY"
    )

with status_col:

    st.success("● SYSTEM ONLINE")

# ============================================================
# INTRODUCTION
# ============================================================

st.subheader("CHPP Production Intelligence")

st.info(
    "Use the navigation menu to enter daily production data "
    "or view calculated production performance indicators."
)

# ============================================================
# SYSTEM MODULES
# ============================================================

st.subheader("System Modules")

module1, module2 = st.columns(2)

with module1:

    with st.container(border=True):

        st.markdown("### 📝 Production Input")

        st.write(
            "Enter daily CHPP production data, production streams, "
            "feeder tonnage and operating hours."
        )

        st.caption(
            "Operator module"
        )

with module2:

    with st.container(border=True):

        st.markdown("### 📊 Production KPIs")

        st.write(
            "View calculated production, throughput, availability, "
            "utilization, recovery, quality and OEE indicators."
        )

        st.caption(
            "Management and performance module"
        )

# ============================================================
# SYSTEM INFORMATION
# ============================================================

st.subheader("System Information")

info1, info2, info3 = st.columns(3)

with info1:

    st.metric(
        label="Plant",
        value="CHPP"
    )

with info2:

    st.metric(
        label="System Status",
        value="Online"
    )

with info3:

    st.metric(
        label="Data Mode",
        value="Production"
    )

# ============================================================
# CURRENT USER INFORMATION
# ============================================================

st.subheader("Current Session")

session_col1, session_col2, session_col3 = st.columns(3)

with session_col1:

    st.metric(
        label="Username",
        value=user.get("username", "—")
    )

with session_col2:

    st.metric(
        label="User",
        value=user.get("full_name", "—")
    )

with session_col3:

    st.metric(
        label="Role",
        value=user.get("role", "—")
    )

# ============================================================
# CURRENT DATE
# ============================================================

st.caption(
    f"Selected production date: "
    f"{production_date.strftime('%d/%m/%Y')}"
)

# ============================================================
# FOOTER
# ============================================================

st.divider()

st.markdown(
    """
    <div class="footer-text">
        <strong>Designed & Developed by Levy Mukopeka</strong><br>
        <em>Digital Systems</em>
    </div>
    """,
    unsafe_allow_html=True
)