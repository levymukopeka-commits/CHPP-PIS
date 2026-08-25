"""
CHPP-PIS — 06_User_Management.py

Internal username/password management for CHPP-PIS.

Authentication model:
- Username only — NO email addresses.
- Passwords are stored as salted scrypt hashes, never plaintext.
- Roles:
    Administrator
    Management
    Supervisor
    Operator
    Viewer
- Administrators can create, activate/deactivate, and reset users.
- The page stores the authenticated user in st.session_state.

IMPORTANT:
This module expects a Supabase table named:
    public.chpp_users

Run the supplied SQL setup script once in Supabase before using this page.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = object


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="CHPP-PIS User Management",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

TABLE_NAME = "chpp_users"

ROLES = [
    "Administrator",
    "Management",
    "Supervisor",
    "Operator",
    "Viewer",
]

ROLE_DESCRIPTIONS = {
    "Administrator": "Full system access and user administration.",
    "Management": "Management dashboards and analytical information.",
    "Supervisor": "Production input, KPIs and equipment information.",
    "Operator": "Production input access.",
    "Viewer": "Read-only dashboard access.",
}

MIN_PASSWORD_LENGTH = 8

# scrypt parameters. These are intentionally kept in the application so
# password verification remains independent of external password packages.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64


# ============================================================
# LOAD .ENV
# ============================================================

if load_dotenv is not None:
    try:
        project_root = Path(__file__).resolve().parent.parent
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(dotenv_path=env_file, override=False)
    except Exception:
        pass


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
<style>
    .main-title {
        font-size: 40px;
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

    .user-card {
        background: #111923;
        border: 1px solid #263548;
        border-radius: 12px;
        padding: 18px;
        min-height: 130px;
    }

    .user-name {
        font-size: 22px;
        font-weight: 800;
        color: #f4f7fb;
    }

    .user-meta {
        color: #8da6c4;
        font-size: 13px;
        margin-top: 7px;
    }

    .role-card {
        background: #111923;
        border: 1px solid #263548;
        border-radius: 10px;
        padding: 14px;
        min-height: 110px;
    }

    .role-title {
        color: #5ea1ff;
        font-weight: 800;
        font-size: 14px;
    }

    .role-description {
        color: #aab7c7;
        font-size: 12px;
        margin-top: 7px;
        line-height: 1.45;
    }

    .security-box {
        background: #12243a;
        border-left: 4px solid #5ea1ff;
        border-radius: 8px;
        padding: 13px 16px;
        color: #c9d7e8;
        margin: 10px 0;
    }

    .warning-box {
        background: #302b14;
        border-left: 4px solid #e7b93f;
        border-radius: 8px;
        padding: 13px 16px;
        color: #eee1ad;
        margin: 10px 0;
    }

    .danger-box {
        background: #321d22;
        border-left: 4px solid #ef6464;
        border-radius: 8px;
        padding: 13px 16px;
        color: #f2c5c5;
        margin: 10px 0;
    }

    div[data-testid="stMetric"] {
        background: #111923;
        border: 1px solid #263548;
        border-radius: 12px;
        padding: 14px;
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
            "The Supabase Python package is not installed."
        )

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url:
        raise RuntimeError(
            "SUPABASE_URL is missing from the CHPP-PIS .env file."
        )

    if not key:
        raise RuntimeError(
            "SUPABASE_KEY is missing from the CHPP-PIS .env file."
        )

    return create_client(url, key)


# ============================================================
# PASSWORD SECURITY
# ============================================================

def hash_password(password: str) -> str:
    """
    Create a salted scrypt password hash.

    Stored format:
        scrypt$N$r$p$salt_b64$hash_b64
    """
    salt = secrets.token_bytes(16)

    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )

    return (
        f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(derived).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        parts = stored_hash.split("$")

        if len(parts) != 6:
            return False

        algorithm, n, r, p, salt_b64, hash_b64 = parts

        if algorithm != "scrypt":
            return False

        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)

        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )

        return hmac.compare_digest(actual, expected)

    except Exception:
        return False


def validate_username(username: str) -> tuple[bool, str]:
    username = username.strip()

    if len(username) < 3:
        return False, "Username must contain at least 3 characters."

    if len(username) > 30:
        return False, "Username cannot exceed 30 characters."

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return (
            False,
            "Use only letters, numbers, underscore, hyphen or period.",
        )

    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < MIN_PASSWORD_LENGTH:
        return (
            False,
            f"Password must contain at least {MIN_PASSWORD_LENGTH} characters.",
        )

    if password.strip() != password:
        return False, "Password cannot start or end with spaces."

    return True, ""


# ============================================================
# USER DATA ACCESS
# ============================================================

def get_users() -> list[dict]:
    client = get_supabase()

    response = (
        client
        .table(TABLE_NAME)
        .select(
            "id,username,full_name,role,is_active,created_at,last_login"
        )
        .order("username", desc=False)
        .execute()
    )

    return response.data or []


def get_user_by_username(username: str) -> Optional[dict]:
    client = get_supabase()

    response = (
        client
        .table(TABLE_NAME)
        .select("*")
        .eq("username", username.strip())
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


def create_user_record(
    username: str,
    full_name: str,
    role: str,
    password: str,
) -> None:

    client = get_supabase()

    record = {
        "username": username.strip(),
        "full_name": full_name.strip(),
        "role": role,
        "password_hash": hash_password(password),
        "is_active": True,
    }

    client.table(TABLE_NAME).insert(record).execute()


def update_user_record(
    user_id: str,
    full_name: str,
    role: str,
    is_active: bool,
) -> None:

    client = get_supabase()

    client.table(TABLE_NAME).update(
        {
            "full_name": full_name.strip(),
            "role": role,
            "is_active": bool(is_active),
        }
    ).eq("id", user_id).execute()


def reset_user_password(
    user_id: str,
    new_password: str,
) -> None:

    client = get_supabase()

    client.table(TABLE_NAME).update(
        {
            "password_hash": hash_password(new_password),
        }
    ).eq("id", user_id).execute()


def update_last_login(user_id: str) -> None:
    client = get_supabase()

    client.table(TABLE_NAME).update(
        {
            "last_login": pd.Timestamp.utcnow().isoformat(),
        }
    ).eq("id", user_id).execute()


def count_active_admins(users: list[dict]) -> int:
    return sum(
        1
        for user in users
        if user.get("role") == "Administrator"
        and bool(user.get("is_active"))
    )


# ============================================================
# LOGIN STATE
# ============================================================

def is_logged_in() -> bool:
    return bool(
        st.session_state.get("authenticated_user")
    )


def current_user() -> Optional[dict]:
    return st.session_state.get(
        "authenticated_user"
    )


def logout() -> None:
    st.session_state.pop(
        "authenticated_user",
        None,
    )
    st.rerun()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## 🏭 CHPP-PIS")
    st.caption("Production Intelligence System")
    st.divider()

    if is_logged_in():
        user = current_user()

        st.markdown("### SIGNED IN")
        st.success(
            f"👤 {user.get('full_name') or user.get('username')}"
        )
        st.caption(
            f"Username: {user.get('username')}"
        )
        st.caption(
            f"Role: {user.get('role')}"
        )

        st.divider()

        if st.button(
            "↪ Logout",
            use_container_width=True,
        ):
            logout()

    else:
        st.markdown("### ACCESS")
        st.caption("Not signed in")


# ============================================================
# PAGE HEADER
# ============================================================

left, right = st.columns(
    [5, 1],
    vertical_alignment="center",
)

with left:
    st.markdown(
        '<div class="main-title">👥 User Management</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="subtitle">'
        "Username-based access control • roles • password management"
        "</div>",
        unsafe_allow_html=True,
    )

with right:
    st.markdown(
        '<div class="status">● SECURITY MODULE</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# CONNECTION CHECK
# ============================================================

try:
    users = get_users()
except Exception as exc:
    st.error(
        "The User Management database table is not ready yet."
    )

    st.markdown(
        """
        <div class="warning-box">
            <strong>Required setup:</strong><br><br>
            Create the <code>chpp_users</code> table in Supabase using the
            SQL setup file supplied with this module.
            <br><br>
            The exact database error is shown below for troubleshooting.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.code(str(exc), language="text")
    st.stop()


# ============================================================
# FIRST-USER BOOTSTRAP
# ============================================================

if len(users) == 0:

    st.markdown(
        '<div class="section-title">INITIAL ADMINISTRATOR SETUP</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="security-box">
            <strong>No users exist yet.</strong><br><br>
            Create the first CHPP-PIS Administrator account. This account
            will control all subsequent user creation and access.
            <br><br>
            Use a strong password and do not share the Administrator account.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form(
        "first_admin_form",
        clear_on_submit=False,
    ):

        username = st.text_input(
            "Administrator Username",
            placeholder="e.g. admin",
        )

        full_name = st.text_input(
            "Full Name",
            placeholder="e.g. CHPP Administrator",
        )

        password = st.text_input(
            "Password",
            type="password",
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Create Administrator",
            use_container_width=True,
            type="primary",
        )

    if submitted:

        valid_username, username_error = (
            validate_username(username)
        )

        valid_password, password_error = (
            validate_password(password)
        )

        if not valid_username:
            st.error(username_error)
        elif not full_name.strip():
            st.error("Full Name is required.")
        elif not valid_password:
            st.error(password_error)
        elif password != confirm_password:
            st.error("Passwords do not match.")
        else:
            try:
                create_user_record(
                    username=username,
                    full_name=full_name,
                    role="Administrator",
                    password=password,
                )

                st.success(
                    "Administrator created successfully. "
                    "Please sign in below."
                )

                st.rerun()

            except Exception as exc:
                st.error(
                    f"Unable to create Administrator: {exc}"
                )

    st.stop()


# ============================================================
# LOGIN
# ============================================================

if not is_logged_in():

    st.markdown(
        '<div class="section-title">SYSTEM LOGIN</div>',
        unsafe_allow_html=True,
    )

    login_left, login_right = st.columns(
        [1.2, 1],
        gap="large",
    )

    with login_left:

        with st.form(
            "login_form",
            clear_on_submit=True,
        ):

            username = st.text_input(
                "Username",
                placeholder="Enter username",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter password",
            )

            submitted = st.form_submit_button(
                "LOGIN",
                use_container_width=True,
                type="primary",
            )

        if submitted:

            if not username.strip() or not password:
                st.error(
                    "Enter both username and password."
                )
            else:

                try:
                    user = get_user_by_username(
                        username
                    )

                    if (
                        user
                        and bool(user.get("is_active"))
                        and verify_password(
                            password,
                            user.get(
                                "password_hash",
                                "",
                            ),
                        )
                    ):

                        update_last_login(
                            str(user["id"])
                        )

                        st.session_state[
                            "authenticated_user"
                        ] = {
                            "id": user["id"],
                            "username": user["username"],
                            "full_name": user.get(
                                "full_name",
                                "",
                            ),
                            "role": user["role"],
                        }

                        st.success(
                            "Login successful."
                        )

                        st.rerun()

                    elif user and not bool(
                        user.get("is_active")
                    ):
                        st.error(
                            "This user account is inactive. "
                            "Contact an Administrator."
                        )

                    else:
                        st.error(
                            "Invalid username or password."
                        )

                except Exception as exc:
                    st.error(
                        f"Unable to process login: {exc}"
                    )

    with login_right:

        st.markdown(
            """
            <div class="security-box">
                <strong>CHPP-PIS Access</strong><br><br>
                Login uses a username and password only.
                No email address is required.
                <br><br>
                Passwords are stored as salted scrypt hashes and are never
                displayed or stored as plain text.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="section-title">AVAILABLE ROLES</div>',
        unsafe_allow_html=True,
    )

    role_cols = st.columns(len(ROLES))

    for col, role in zip(role_cols, ROLES):

        with col:
            st.markdown(
                f"""
                <div class="role-card">
                    <div class="role-title">{role}</div>
                    <div class="role-description">
                        {ROLE_DESCRIPTIONS[role]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.stop()


# ============================================================
# AUTHENTICATED USER
# ============================================================

user = current_user()

if not user:
    st.stop()

user_role = user.get("role")

if user_role != "Administrator":

    st.markdown(
        '<div class="section-title">ACCOUNT</div>',
        unsafe_allow_html=True,
    )

    account_col1, account_col2 = st.columns(2)

    with account_col1:
        st.markdown(
            f"""
            <div class="user-card">
                <div class="user-name">
                    {user.get("full_name") or user.get("username")}
                </div>
                <div class="user-meta">
                    Username: {user.get("username")}
                </div>
                <div class="user-meta">
                    Role: {user_role}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with account_col2:
        st.markdown(
            """
            <div class="security-box">
                User administration is restricted to the
                <strong>Administrator</strong> role.
                <br><br>
                Contact an Administrator if you need a new account,
                role change, activation/deactivation, or password reset.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="section-title">ROLE INFORMATION</div>',
        unsafe_allow_html=True,
    )

    st.info(
        ROLE_DESCRIPTIONS.get(
            user_role,
            "Access is controlled by your assigned role.",
        )
    )

    st.stop()


# ============================================================
# ADMIN DASHBOARD
# ============================================================

st.markdown(
    '<div class="section-title">ADMINISTRATOR CONTROL CENTER</div>',
    unsafe_allow_html=True,
)

active_users = sum(
    1
    for item in users
    if bool(item.get("is_active"))
)

inactive_users = len(users) - active_users
admin_count = count_active_admins(users)

metrics = st.columns(4)

with metrics[0]:
    st.metric(
        "Total Users",
        len(users),
    )

with metrics[1]:
    st.metric(
        "Active Users",
        active_users,
    )

with metrics[2]:
    st.metric(
        "Inactive Users",
        inactive_users,
    )

with metrics[3]:
    st.metric(
        "Active Administrators",
        admin_count,
    )


if admin_count == 1:
    st.markdown(
        """
        <div class="warning-box">
            <strong>Administrator protection:</strong>
            You currently have only one active Administrator. Create another
            Administrator account before deactivating the existing one.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# CREATE USER
# ============================================================

st.markdown(
    '<div class="section-title">CREATE USER</div>',
    unsafe_allow_html=True,
)

with st.expander(
    "＋ Create New User",
    expanded=False,
):

    with st.form(
        "create_user_form",
        clear_on_submit=True,
    ):

        col1, col2 = st.columns(2)

        with col1:
            new_username = st.text_input(
                "Username",
                placeholder="e.g. operator01",
            )

            new_full_name = st.text_input(
                "Full Name",
                placeholder="e.g. John Banda",
            )

        with col2:
            new_role = st.selectbox(
                "Role",
                ROLES,
            )

            new_password = st.text_input(
                "Temporary Password",
                type="password",
            )

        new_confirm = st.text_input(
            "Confirm Password",
            type="password",
        )

        create_submitted = st.form_submit_button(
            "Create User",
            use_container_width=True,
            type="primary",
        )

    if create_submitted:

        valid_username, username_error = (
            validate_username(new_username)
        )

        valid_password, password_error = (
            validate_password(new_password)
        )

        if not valid_username:
            st.error(username_error)

        elif not new_full_name.strip():
            st.error("Full Name is required.")

        elif not valid_password:
            st.error(password_error)

        elif new_password != new_confirm:
            st.error("Passwords do not match.")

        else:

            try:
                existing = get_user_by_username(
                    new_username
                )

                if existing:
                    st.error(
                        "That username already exists."
                    )
                else:

                    create_user_record(
                        username=new_username,
                        full_name=new_full_name,
                        role=new_role,
                        password=new_password,
                    )

                    st.success(
                        f"User '{new_username.strip()}' "
                        "created successfully."
                    )

                    st.cache_data.clear()
                    st.rerun()

            except Exception as exc:
                st.error(
                    f"Unable to create user: {exc}"
                )


# ============================================================
# USER LIST
# ============================================================

st.markdown(
    '<div class="section-title">USER ACCOUNTS</div>',
    unsafe_allow_html=True,
)

users = get_users()

display_rows = []

for item in users:

    created = item.get("created_at")
    last_login = item.get("last_login")

    if created:
        try:
            created = pd.Timestamp(
                created
            ).strftime(
                "%d/%m/%Y %H:%M"
            )
        except Exception:
            pass

    if last_login:
        try:
            last_login = pd.Timestamp(
                last_login
            ).strftime(
                "%d/%m/%Y %H:%M"
            )
        except Exception:
            pass

    display_rows.append(
        {
            "Username": item.get("username"),
            "Full Name": item.get("full_name"),
            "Role": item.get("role"),
            "Status": (
                "Active"
                if bool(item.get("is_active"))
                else "Inactive"
            ),
            "Created": created or "—",
            "Last Login": last_login or "Never",
        }
    )

users_df = pd.DataFrame(display_rows)

st.dataframe(
    users_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# MANAGE EXISTING USER
# ============================================================

st.markdown(
    '<div class="section-title">MANAGE USER</div>',
    unsafe_allow_html=True,
)

user_lookup = {
    item["username"]: item
    for item in users
    if item.get("username")
}

selected_username = st.selectbox(
    "Select User",
    list(user_lookup.keys()),
)

selected_user = user_lookup[selected_username]

with st.form(
    "manage_user_form",
    clear_on_submit=False,
):

    col1, col2 = st.columns(2)

    with col1:

        edit_full_name = st.text_input(
            "Full Name",
            value=selected_user.get(
                "full_name",
                "",
            ),
        )

        edit_role = st.selectbox(
            "Role",
            ROLES,
            index=(
                ROLES.index(
                    selected_user.get(
                        "role",
                        "Viewer",
                    )
                )
                if selected_user.get("role") in ROLES
                else len(ROLES) - 1
            ),
        )

    with col2:

        edit_active = st.checkbox(
            "Account Active",
            value=bool(
                selected_user.get(
                    "is_active"
                )
            ),
        )

        st.caption(
            f"Username: {selected_username}"
        )

    save_user = st.form_submit_button(
        "Save User Changes",
        use_container_width=True,
    )

if save_user:

    # Never allow an Administrator to deactivate the final
    # active Administrator.
    if (
        selected_user.get("role") == "Administrator"
        and bool(selected_user.get("is_active"))
        and not edit_active
        and admin_count <= 1
    ):
        st.error(
            "You cannot deactivate the last active Administrator."
        )

    elif (
        selected_user.get("id") == user.get("id")
        and selected_user.get("role") == "Administrator"
        and edit_role != "Administrator"
    ):
        st.error(
            "You cannot remove your own Administrator role."
        )

    elif (
        selected_user.get("id") == user.get("id")
        and not edit_active
    ):
        st.error(
            "You cannot deactivate your own account."
        )

    else:

        try:
            update_user_record(
                user_id=str(
                    selected_user["id"]
                ),
                full_name=edit_full_name,
                role=edit_role,
                is_active=edit_active,
            )

            # Keep the current session consistent if the Administrator
            # changes their own full name.
            if (
                str(selected_user["id"])
                == str(user.get("id"))
            ):
                st.session_state[
                    "authenticated_user"
                ]["full_name"] = edit_full_name
                st.session_state[
                    "authenticated_user"
                ]["role"] = edit_role

            st.success(
                f"User '{selected_username}' updated successfully."
            )

            st.cache_data.clear()
            st.rerun()

        except Exception as exc:
            st.error(
                f"Unable to update user: {exc}"
            )


# ============================================================
# RESET PASSWORD
# ============================================================

st.markdown(
    '<div class="section-title">PASSWORD MANAGEMENT</div>',
    unsafe_allow_html=True,
)

with st.expander(
    f"🔐 Reset Password — {selected_username}",
    expanded=False,
):

    with st.form(
        "reset_password_form",
        clear_on_submit=True,
    ):

        reset_password_value = st.text_input(
            "New Password",
            type="password",
        )

        reset_confirm = st.text_input(
            "Confirm New Password",
            type="password",
        )

        reset_submitted = st.form_submit_button(
            "Reset Password",
            use_container_width=True,
            type="primary",
        )

    if reset_submitted:

        valid_password, password_error = (
            validate_password(
                reset_password_value
            )
        )

        if not valid_password:
            st.error(password_error)

        elif reset_password_value != reset_confirm:
            st.error(
                "Passwords do not match."
            )

        else:

            try:
                reset_user_password(
                    user_id=str(
                        selected_user["id"]
                    ),
                    new_password=reset_password_value,
                )

                st.success(
                    f"Password for '{selected_username}' "
                    "was reset successfully."
                )

            except Exception as exc:
                st.error(
                    f"Unable to reset password: {exc}"
                )


# ============================================================
# ROLE MATRIX
# ============================================================

st.markdown(
    '<div class="section-title">ROLE ACCESS MODEL</div>',
    unsafe_allow_html=True,
)

role_matrix = pd.DataFrame(
    [
        {
            "Role": "Administrator",
            "Production Input": "Full",
            "KPIs": "Full",
            "Equipment": "Full",
            "Analytics": "Full",
            "Management": "Full",
            "User Management": "Full",
        },
        {
            "Role": "Management",
            "Production Input": "Read",
            "KPIs": "Read",
            "Equipment": "Read",
            "Analytics": "Read",
            "Management": "Read",
            "User Management": "No",
        },
        {
            "Role": "Supervisor",
            "Production Input": "Full",
            "KPIs": "Read",
            "Equipment": "Read",
            "Analytics": "Read",
            "Management": "Read",
            "User Management": "No",
        },
        {
            "Role": "Operator",
            "Production Input": "Full",
            "KPIs": "Read",
            "Equipment": "Read",
            "Analytics": "No",
            "Management": "No",
            "User Management": "No",
        },
        {
            "Role": "Viewer",
            "Production Input": "No",
            "KPIs": "Read",
            "Equipment": "Read",
            "Analytics": "Read",
            "Management": "Read",
            "User Management": "No",
        },
    ]
)

st.dataframe(
    role_matrix,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# SECURITY NOTES
# ============================================================

st.markdown(
    '<div class="section-title">SECURITY STATUS</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="security-box">
        <strong>Current security design</strong><br><br>
        • Username-based login — no email required.<br>
        • Passwords are salted and hashed with scrypt.<br>
        • Plain-text passwords are never stored in the database.<br>
        • Inactive accounts cannot log in.<br>
        • Only Administrators can manage users.<br>
        • The last active Administrator cannot be deactivated.<br>
        • User roles are stored in the database and can be changed by an
        Administrator.
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    "Next integration step: apply the same login/role guard to the "
    "Production Input, KPI, Equipment, Analytics and Management pages."
)


# ============================================================
# FOOTER
# ============================================================
