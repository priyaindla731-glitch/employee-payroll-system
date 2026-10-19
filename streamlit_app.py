import streamlit as st
import pandas as pd
import hashlib
import hmac
import secrets
from datetime import date, datetime
from io import BytesIO

import database as db
from payroll import calculate_salary
from payslip import generate_payslip


# ---------------- PAGE SETTINGS ----------------

st.set_page_config(
    page_title="Employee Payroll Management",
    page_icon="💼",
    layout="wide",
)

db.init_db()


# ---------------- PASSWORD HELPERS ----------------

def hash_password(password):
    salt = secrets.token_hex(16)
    iterations = 200000
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"{iterations}${salt}${digest}"


def verify_password(password, stored_hash):
    try:
        iterations, salt, expected = stored_hash.split("$")
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False


def money(value):
    return f"₹{float(value or 0):,.2f}"


def log_action(username, action, details=""):
    try:
        db.add_audit_log(username, action, details)
    except Exception:
        pass


# ---------------- SESSION ----------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = None

if "username" not in st.session_state:
    st.session_state.username = None

if "employee_id" not in st.session_state:
    st.session_state.employee_id = None


# ---------------- STYLE ----------------

st.markdown(
    """
    <style>
    .stApp {
        background-color: #f4f6fc;
    }
    [data-testid="stMetric"] {
        background: white;
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #e4e7f0;
    }
    h1, h2, h3 {
        color: #253858;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------- LOGIN ----------------

def login_page():
    st.title("💼 Employee Payroll Management System")
    st.write("Secure employee and payroll management")

    left, center, right = st.columns([1, 1.4, 1])

    with center:
        with st.container(border=True):
            st.subheader("Sign in")

            login_type = st.radio(
                "Login as",
                ["Admin", "Employee"],
                horizontal=True,
            )

            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input(
                    "Password",
                    type="password",
                )
                submitted = st.form_submit_button(
                    "Login",
                    use_container_width=True,
                )

            if submitted:
                username = username.strip()

                if not username or not password:
                    st.error("Enter both username and password.")
                    return

                if login_type == "Admin":
                    try:
                        admin_username = st.secrets["ADMIN_USERNAME"]
                        admin_password = st.secrets["ADMIN_PASSWORD"]
                    except Exception:
                        st.error(
                            "Admin credentials are not configured. "
                            "Set ADMIN_USERNAME and ADMIN_PASSWORD "
                            "in Streamlit Cloud → Settings → Secrets."
                        )
                        return

                    if (
                        hmac.compare_digest(username, str(admin_username))
                        and hmac.compare_digest(
                            password, str(admin_password)
                        )
                    ):
                        st.session_state.logged_in = True
                        st.session_state.role = "admin"
                        st.session_state.username = username
                        st.session_state.employee_id = None
                        log_action(username, "Admin login")
                        st.rerun()
                    else:
                        st.error("Invalid admin username or password.")

                else:
                    employee = db.fetch_one(
                        """
                        SELECT id, name, username, password_hash
                        FROM employees
                        WHERE username = ?
                        """,
                        (username,),
                    )

                    if (
                        employee
                        and employee.get("password_hash")
                        and verify_password(
                            password, employee["password_hash"]
                        )
                    ):
                        st.session_state.logged_in = True
                        st.session_state.role = "employee"
                        st.session_state.username = username
                        st.session_state.employee_id = employee["id"]
                        log_action(username, "Employee login")
                        st.rerun()
                    else:
                        st.error(
                            "Invalid employee login. Ask your admin "
                            "to create your account or reset your password."
                        )

    st.caption(
        "For privacy, use test employee data until you have "
        "configured reliable persistent database storage."
    )


# ---------------- DATA HELPERS ----------------

def employee_options():
    employees = db.get_employees()
    return {
        f'{e["name"]} (ID {e["id"]})': e["id"]
        for e in employees
    }


def show_employee_table(employees):
    if not employees:
        st.info("No employee records yet.")
        return

    safe_rows = []
    for e in employees:
        safe_rows.append({
            "ID": e.get("id"),
            "Name": e.get("name"),
            "Email": e.get("email"),
            "Phone": e.get("phone"),
            "Department": e.get("department"),
            "Designation": e.get("designation"),
            "Basic Salary": e.get("basic_salary"),
            "Allowances": e.get("allowances"),
            "Joining Date": e.get("joining_date"),
        })

    st.dataframe(
        pd.DataFrame(safe_rows),
        use_container_width=True,
        hide_index=True,
    )


# ---------------- ADMIN DASHBOARD ----------------

def admin_dashboard():
    st.title("💼 Admin Dashboard")
    st.caption("Manage employees, attendance, leave and payroll.")

    employees = db.get_employees()
    payroll_records = db.get_payroll_records()
    leave_records = db.get_leave_requests()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Employees", len(employees))
    col2.metric("Payroll Records", len(payroll_records))
    col3.metric(
        "Pending Leaves",
        sum(1 for x in leave_records if x["status"] == "Pending"),
    )
    col4.metric(
        "Payroll Total",
        money(sum(float(x.get("net_salary") or 0)
                  for x in payroll_records)),
    )

    tabs = st.tabs([
        "Employees",
        "Payroll",
        "Attendance",
        "Leave Requests",
        "Reports & Audit",
    ])

    # -------- EMPLOYEES --------

    with tabs[0]:
        st.subheader("Employee Directory")
        search = st.text_input("Search by name, email or department")

        filtered = [
            e for e in employees
            if search.lower() in " ".join([
                str(e.get("name") or ""),
                str(e.get("email") or ""),
                str(e.get("department") or ""),
            ]).lower()
        ] if search else employees

        show_employee_table(filtered)

        with st.expander("➕ Add Employee"):
            with st.form("add_employee_form"):
                name = st.text_input("Full name")
                email = st.text_input("Email")
                phone = st.text_input("Phone")
                department = st.text_input("Department")
                designation = st.text_input("Designation")
                basic_salary = st.number_input(
                    "Basic salary (₹)", min_value=0.0, step=500.0
                )
                allowances = st.number_input(
                    "Monthly allowances (₹)", min_value=0.0, step=100.0
                )
                joining_date = st.date_input("Joining date", value=date.today())
                username = st.text_input("Employee login username")
                employee_password = st.text_input(
                    "Initial employee password",
                    type="password",
                )

                create_employee = st.form_submit_button("Add Employee")

            if create_employee:
                if not name.strip() or not username.strip() or not employee_password:
                    st.error(
                        "Name, username, and initial password are required."
                    )
                elif len(employee_password) < 8:
                    st.error("Use an initial password of at least 8 characters.")
                else:
                    try:
                        db.add_employee(
                            name=name.strip(),
                            email=email.strip() or None,
                            phone=phone.strip() or None,
                            department=department.strip() or None,
                            designation=designation.strip() or None,
                            basic_salary=basic_salary,
                            allowances=allowances,
                            joining_date=joining_date.isoformat(),
                            username=username.strip(),
                            password_hash=hash_password(employee_password),
                        )
                        log_action(
                            st.session_state.username,
                            "Added employee",
                            name.strip(),
                        )
                        st.success(
                            "Employee created. Share the login details "
                            "privately with the employee."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(
                            "Could not add employee. Check that the "
                            "username and email are not already in use."
                        )

        with st.expander("✏️ Edit Employee"):
            if employees:
                employee_map = employee_options()
                selected_label = st.selectbox(
                    "Select employee",
                    list(employee_map.keys()),
                    key="edit_employee_select",
                )
                selected_id = employee_map[selected_label]
                selected_employee = db.get_employee(selected_id)

                with st.form("edit_employee_form"):
                    edit_name = st.text_input(
                        "Name",
                        value=selected_employee.get("name") or "",
                    )
                    edit_email = st.text_input(
                        "Email",
                        value=selected_employee.get("email") or "",
                    )
                    edit_phone = st.text_input(
                        "Phone",
                        value=selected_employee.get("phone") or "",
                    )
                    edit_department = st.text_input(
                        "Department",
                        value=selected_employee.get("department") or "",
                    )
                    edit_designation = st.text_input(
                        "Designation",
                        value=selected_employee.get("designation") or "",
                    )
                    edit_basic = st.number_input(
                        "Basic salary (₹)",
                        min_value=0.0,
                        value=float(selected_employee.get("basic_salary") or 0),
                    )
                    edit_allowances = st.number_input(
                        "Allowances (₹)",
                        min_value=0.0,
                        value=float(selected_employee.get("allowances") or 0),
                    )
                    edit_joining = st.text_input(
                        "Joining date (YYYY-MM-DD)",
                        value=selected_employee.get("joining_date") or "",
                    )
                    save_employee = st.form_submit_button("Save Employee")

                if save_employee:
                    try:
                        db.update_employee(
                            selected_id,
                            name=edit_name.strip(),
                            email=edit_email.strip() or None,
                            phone=edit_phone.strip() or None,
                            department=edit_department.strip() or None,
                            designation=edit_designation.strip() or None,
                            basic_salary=edit_basic,
                            allowances=edit_allowances,
                            joining_date=edit_joining.strip() or None,
                        )
                        log_action(
                            st.session_state.username,
                            "Updated employee",
                            str(selected_id),
                        )
                        st.success("Employee updated.")
                        st.rerun()
                    except Exception:
                        st.error(
                            "Could not update employee. Check for duplicate email."
                        )
            else:
                st.info("Add an employee first.")

        with st.expander("🔑 Reset Employee Password"):
            if employees:
                employee_map = employee_options()
                selected_label = st.selectbox(
                    "Employee account",
                    list(employee_map.keys()),
                    key="reset_employee_select",
                )
                new_password = st.text_input(
                    "New password (minimum 8 characters)",
                    type="password",
                )
                if st.button("Reset password"):
                    if len(new_password) < 8:
                        st.error("Password must be at least 8 characters.")
                    else:
                        db.update_employee(
                            employee_map[selected_label],
                            password_hash=hash_password(new_password),
                        )
                        log_action(
                            st.session_state.username,
                            "Reset employee password",
                            str(employee_map[selected_label]),
                        )
                        st.success("Password reset successfully.")
            else:
                st.info("Add an employee first.")

    # -------- PAYROLL --------

    with tabs[1]:
        st.subheader("Process Monthly Payroll")

        if not employees:
            st.info("Add employees before processing payroll.")
        else:
            employee_map = employee_options()

            with st.form("payroll_form"):
                chosen_label = st.selectbox(
                    "Employee",
                    list(employee_map.keys()),
                )
                salary_month = st.text_input(
                    "Salary month (YYYY-MM)",
                    value=date.today().strftime("%Y-%m"),
                )
                emp = db.get_employee(employee_map[chosen_label])

                basic = st.number_input(
                    "Basic salary (₹)",
                    min_value=0.0,
                    value=float(emp.get("basic_salary") or 0),
                )
                allowances = st.number_input(
                    "Allowances (₹)",
                    min_value=0.0,
                    value=float(emp.get("allowances") or 0),
                )
                overtime = st.number_input(
                    "Overtime (₹)", min_value=0.0
                )
                bonus = st.number_input(
                    "Bonus (₹)", min_value=0.0
                )
                advance = st.number_input(
                    "Advance deduction (₹)", min_value=0.0
                )
                tax = st.number_input(
                    "Tax deduction (₹)", min_value=0.0
                )

                process = st.form_submit_button("Calculate and Save Payroll")

            if process:
                try:
                    if (
                        len(salary_month) != 7
                        or salary_month[4] != "-"
                        or not salary_month[:4].isdigit()
                        or not salary_month[5:].isdigit()
                        or not 1 <= int(salary_month[5:]) <= 12
                    ):
                        raise ValueError(
                            "Enter the salary month as YYYY-MM."
                        )

                    result = calculate_salary(
                        basic_salary=basic,
                        allowances=allowances,
                        overtime=overtime,
                        bonus=bonus,
                        advance=advance,
                        tax=tax,
                    )

                    db.save_payroll(
                        employee_id=emp["id"],
                        salary_month=salary_month,
                        **result,
                    )

                    log_action(
                        st.session_state.username,
                        "Processed payroll",
                        f'Employee {emp["id"]}, {salary_month}',
                    )
                    st.success("Payroll saved successfully.")
                    st.json(result)
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error(
                        "Could not save payroll. Check the database "
                        "and make sure this month has valid records."
                    )

        st.subheader("Payroll Records")
        records = db.get_payroll_records()
        if records:
            st.dataframe(
                pd.DataFrame(records),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No payroll records yet.")

        if records:
            selected_record = st.selectbox(
                "Choose a payroll record for PDF",
                records,
                format_func=lambda r: (
                    f'{r["employee_name"]} — {r["salary_month"]}'
                ),
            )
            if st.button("Generate PDF Payslip"):
                employee = db.get_employee(selected_record["employee_id"])
                pdf_bytes = generate_payslip(employee, selected_record)
                st.download_button(
                    "Download Payslip PDF",
                    data=pdf_bytes,
                    file_name=(
                        f'payslip_{selected_record["employee_id"]}_'
                        f'{selected_record["salary_month"]}.pdf'
                    ),
                    mime="application/pdf",
                )

    # -------- ATTENDANCE --------

    with tabs[2]:
        st.subheader("Record Attendance")

        if employees:
            employee_map = employee_options()
            with st.form("attendance_form"):
                chosen_label = st.selectbox(
                    "Employee",
                    list(employee_map.keys()),
                    key="attendance_employee",
                )
                attendance_date = st.date_input(
                    "Attendance date",
                    value=date.today(),
                )
                status = st.selectbox(
                    "Status",
                    ["Present", "Absent", "Half Day", "On Leave"],
                )
                check_in = st.text_input(
                    "Check-in time (optional, e.g. 09:00)"
                )
                check_out = st.text_input(
                    "Check-out time (optional, e.g. 17:00)"
                )
                attendance_submit = st.form_submit_button("Save Attendance")

            if attendance_submit:
                try:
                    db.mark_attendance(
                        employee_map[chosen_label],
                        attendance_date.isoformat(),
                        check_in.strip() or None,
                        check_out.strip() or None,
                        status,
                    )
                    log_action(
                        st.session_state.username,
                        "Saved attendance",
                        attendance_date.isoformat(),
                    )
                    st.success("Attendance saved.")
                    st.rerun()
                except Exception:
                    st.error("Could not save attendance.")
        else:
            st.info("Add employees first.")

        attendance_records = db.get_attendance()
        if attendance_records:
            st.dataframe(
                pd.DataFrame(attendance_records),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No attendance records yet.")

    # -------- LEAVE REQUESTS --------

    with tabs[3]:
        st.subheader("Leave Requests")

        leaves = db.get_leave_requests()
        if leaves:
            st.dataframe(
                pd.DataFrame(leaves),
                use_container_width=True,
                hide_index=True,
            )
            pending = [x for x in leaves if x["status"] == "Pending"]

            if pending:
                selected_leave = st.selectbox(
                    "Select pending request",
                    pending,
                    format_func=lambda x: (
                        f'{x["employee_name"]}: {x["start_date"]} '
                        f'to {x["end_date"]}'
                    ),
                )
                decision = st.radio(
                    "Decision",
                    ["Approved", "Rejected"],
                    horizontal=True,
                )
                if st.button("Save Leave Decision"):
                    db.update_leave_status(
                        selected_leave["id"], decision
                    )
                    log_action(
                        st.session_state.username,
                        "Updated leave request",
                        f'{selected_leave["id"]}: {decision}',
                    )
                    st.success("Leave decision saved.")
                    st.rerun()
        else:
            st.info("No leave requests yet.")

    # -------- REPORTS & AUDIT --------

    with tabs[4]:
        st.subheader("Reports")

        employees = db.get_employees()
        payroll_records = db.get_payroll_records()
        attendance_records = db.get_attendance()
        leave_records = db.get_leave_requests()

        report_type = st.selectbox(
            "Choose report",
            ["Payroll", "Employees", "Attendance", "Leave Requests"],
        )

        report_map = {
            "Payroll": payroll_records,
            "Employees": employees,
            "Attendance": attendance_records,
            "Leave Requests": leave_records,
        }
        report_rows = report_map[report_type]

        if report_rows:
            df = pd.DataFrame(report_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Download CSV Report",
                data=csv_bytes,
                file_name=f"{report_type.lower().replace(' ', '_')}_report.csv",
                mime="text/csv",
            )

            excel_buffer = BytesIO()
            with pd.ExcelWriter(
                excel_buffer, engine="openpyxl"
            ) as writer:
                df.to_excel(writer, index=False, sheet_name="Report")

            st.download_button(
                "Download Excel Report",
                data=excel_buffer.getvalue(),
                file_name=f"{report_type.lower().replace(' ', '_')}_report.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            )
        else:
            st.info("No records available for this report.")

        st.subheader("Recent Audit Log")
        audit_rows = db.get_audit_logs(limit=100)
        if audit_rows:
            st.dataframe(
                pd.DataFrame(audit_rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No audit entries yet.")


# ---------------- EMPLOYEE PORTAL ----------------

def employee_portal():
    employee_id = st.session_state.employee_id
    employee = db.get_employee(employee_id)

    if not employee:
        st.error("Your employee profile could not be found.")
        return

    st.title("👤 Employee Self-Service")
    st.write(f'Welcome, **{employee["name"]}**')

    profile_tab, payslip_tab, attendance_tab, leave_tab = st.tabs([
        "My Profile",
        "My Payslips",
        "My Attendance",
        "My Leave",
    ])

    with profile_tab:
        st.subheader("My Profile")
        st.write(f'**Employee ID:** {employee["id"]}')
        st.write(f'**Name:** {employee.get("name") or ""}')
        st.write(f'**Email:** {employee.get("email") or ""}')
        st.write(f'**Phone:** {employee.get("phone") or ""}')
        st.write(f'**Department:** {employee.get("department") or ""}')
        st.write(f'**Designation:** {employee.get("designation") or ""}')
        st.write(
            f'**Basic Salary:** {money(employee.get("basic_salary"))}'
        )

    with payslip_tab:
        st.subheader("My Salary Records")
        records = db.get_payroll_records(employee_id)

        if records:
            st.dataframe(
                pd.DataFrame(records),
                use_container_width=True,
                hide_index=True,
            )

            chosen_record = st.selectbox(
                "Choose salary month",
                records,
                format_func=lambda r: r["salary_month"],
            )
            if st.button("Prepare My Payslip"):
                pdf_bytes = generate_payslip(employee, chosen_record)
                st.download_button(
                    "Download My Payslip",
                    data=pdf_bytes,
                    file_name=(
                        f'payslip_{employee_id}_'
                        f'{chosen_record["salary_month"]}.pdf'
                    ),
                    mime="application/pdf",
                )
        else:
            st.info("Your payroll records are not available yet.")

    with attendance_tab:
        st.subheader("My Attendance")
        records = db.get_attendance(employee_id)
        if records:
            st.dataframe(
                pd.DataFrame(records),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No attendance records available.")

    with leave_tab:
        st.subheader("Submit Leave Request")

        with st.form("employee_leave_form"):
            leave_type = st.selectbox(
                "Leave type",
                ["Casual Leave", "Sick Leave", "Personal Leave", "Other"],
            )
            start_date = st.date_input(
                "Start date",
                value=date.today(),
                key="leave_start",
            )
            end_date = st.date_input(
                "End date",
                value=date.today(),
                key="leave_end",
            )
            reason = st.text_area("Reason")
            submit_leave = st.form_submit_button("Submit Leave Request")

        if submit_leave:
            if end_date < start_date:
                st.error("End date cannot be before start date.")
            else:
                db.add_leave_request(
                    employee_id,
                    leave_type,
                    start_date.isoformat(),
                    end_date.isoformat(),
                    reason.strip(),
                )
                log_action(
                    st.session_state.username,
                    "Submitted leave request",
                    f"{start_date} to {end_date}",
                )
                st.success("Your leave request has been submitted.")

        st.subheader("My Leave Requests")
        my_leaves = db.get_leave_requests(employee_id)

        if my_leaves:
            st.dataframe(
                pd.DataFrame(my_leaves),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("You have not submitted any leave requests.")


# ---------------- APP ROUTER ----------------

if not st.session_state.logged_in:
    login_page()
else:
    with st.sidebar:
        st.title("💼 Payroll System")
        st.write(f'User: **{st.session_state.username}**')
        st.write(f'Role: **{st.session_state.role.title()}**')

        if st.button("Logout", use_container_width=True):
            log_action(
                st.session_state.username,
                "Logout",
            )
            st.session_state.logged_in = False
            st.session_state.role = None
            st.session_state.username = None
            st.session_state.employee_id = None
            st.rerun()

    if st.session_state.role == "admin":
        admin_dashboard()
    elif st.session_state.role == "employee":
        employee_portal()
    else:
        st.session_state.logged_in = False
        st.rerun()
