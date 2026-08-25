from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    from supabase import create_client
except Exception:
    create_client = None


# ============================================================
# CHPP-PIS CENTRAL AUTHENTICATION
# ============================================================

TABLE_NAME = "chpp_users"

ROLES = [
    "Administrator",
    "Management",
    "Supervisor",
    "Operator",
    "Viewer",
]

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

if load_dotenv is not None:
    try:
        project_root = Path(__file__).resolve().parent
        env_file = project_root / ".env"

        if env_file.exists():
            load_dotenv(
                dotenv_path=env_file,
                override=False
            )
    except Exception:
        pass


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
            "SUPABASE_URL is missing from the .env file."
        )

    if not key:
        raise RuntimeError(
            "SUPABASE_KEY is missing from the .env file."
        )

    return create_client(url, key)


# ============================================================
# PASSWORD VERIFICATION
# ============================================================

def verify_password(
    password: str,
    stored_hash: str
) -> bool:

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

        return hmac.compare_digest(
            actual,
            expected
        )

    except Exception:
        return False


# ============================================================
# USER LOOKUP
# ============================================================

def get_user_by_username(
    username: str
) -> Optional[dict]:

    client = get_supabase()

    response = (
        client
        .table(TABLE_NAME)
        .select("*")
        .eq(
            "username",
            username.strip()
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


# ============================================================
# LOGIN
# ============================================================

def login(
    username: str,
    password: str
) -> tuple[bool, str]:

    if not username.strip():
        return False, "Username is required."

    if not password:
        return False, "Password is required."

    try:

        user = get_user_by_username(username)

        if not user:
            return False, "Invalid username or password."

        if not bool(user.get("is_active")):
            return (
                False,
                "This user account is inactive."
            )

        if not verify_password(
            password,
            user.get("password_hash", "")
        ):
            return False, "Invalid username or password."

        # Update last login
        try:

            client = get_supabase()

            client.table(TABLE_NAME).update(
                {
                    "last_login":
                        pd.Timestamp.utcnow().isoformat()
                }
            ).eq(
                "id",
                user["id"]
            ).execute()

        except Exception:
            # Login should still succeed even if
            # last-login recording fails.
            pass

        # Store only the information needed by
        # the application session.
        st.session_state[
            "authenticated_user"
        ] = {
            "id": user["id"],
            "username": user["username"],
            "full_name": user.get(
                "full_name",
                ""
            ),
            "role": user["role"],
        }

        return True, "Login successful."

    except Exception as exc:

        return (
            False,
            f"Unable to process login: {exc}"
        )


# ============================================================
# SESSION
# ============================================================

def is_logged_in() -> bool:

    return bool(
        st.session_state.get(
            "authenticated_user"
        )
    )


def current_user() -> Optional[dict]:

    return st.session_state.get(
        "authenticated_user"
    )


def current_role() -> Optional[str]:

    user = current_user()

    if not user:
        return None

    return user.get("role")


# ============================================================
# LOGOUT
# ============================================================

def logout():

    st.session_state.pop(
        "authenticated_user",
        None
    )

    st.rerun()


# ============================================================
# LOGIN PAGE
# ============================================================

def show_login():

    st.markdown(
        """
        <div style="
            max-width:600px;
            margin:80px auto 20px auto;
            text-align:center;
        ">
            <h1>🏭 CHPP-PIS</h1>
            <p>
                Production Intelligence System
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    left, center, right = st.columns(
        [1, 2, 1]
    )

    with center:

        st.markdown(
            "### System Login"
        )

        with st.form(
            "chpp_login_form"
        ):

            username = st.text_input(
                "Username",
                placeholder="Enter username"
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter password"
            )

            submitted = st.form_submit_button(
                "LOGIN",
                use_container_width=True,
                type="primary"
            )

        if submitted:

            success, message = login(
                username,
                password
            )

            if success:

                st.success(message)

                st.rerun()

            else:

                st.error(message)

        st.caption(
            "Username-based access • No email required"
        )


# ============================================================
# REQUIRE LOGIN
# ============================================================

def require_login(
    allowed_roles: Optional[list[str]] = None
):

    if not is_logged_in():

        show_login()
        st.stop()

    user = current_user()

    if allowed_roles is not None:

        if user.get("role") not in allowed_roles:

            st.error(
                "You do not have permission "
                "to access this page."
            )

            st.stop()

    return user


# ============================================================
# ROLE CHECK
# ============================================================

def has_role(
    role: str
) -> bool:

    return current_role() == role


def has_any_role(
    roles: list[str]
) -> bool:

    role = current_role()

    return role in roles


# ============================================================
# SIDEBAR USER STATUS
# ============================================================

def show_user_sidebar():

    user = current_user()

    if not user:
        return

    with st.sidebar:

        st.divider()

        st.markdown(
            "### SIGNED IN"
        )

        st.success(
            f"👤 {user.get('full_name') or user.get('username')}"
        )

        st.caption(
            f"Username: {user.get('username')}"
        )

        st.caption(
            f"Role: {user.get('role')}"
        )

        if st.button(
            "↪ Logout",
            use_container_width=True
        ):

            logout()