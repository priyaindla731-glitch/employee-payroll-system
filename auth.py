import hmac
import streamlit as st


def show_login():
    st.title("🔐 Admin Login")
    st.write("Sign in to manage employee payroll records.")

    with st.form("admin_login"):
        username = st.text_input("Username")
        password = st.text_input(
            "Password",
            type="password"
        )
        submitted = st.form_submit_button("Login")

    if submitted:
        expected_username = st.secrets.get(
            "ADMIN_USERNAME", ""
        )
        expected_password = st.secrets.get(
            "ADMIN_PASSWORD", ""
        )

        if not expected_username or not expected_password:
            st.error("Admin credentials are not configured.")
            return False

        valid_username = hmac.compare_digest(
            username, expected_username
        )
        valid_password = hmac.compare_digest(
            password, expected_password
        )

        if valid_username and valid_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    return st.session_state.get("authenticated", False)


def logout():
    st.session_state["authenticated"] = False
    st.rerun()
