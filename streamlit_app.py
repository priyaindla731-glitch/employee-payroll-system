import streamlit as st
import pandas as pd
import sqlite3
import io
import hmac
from datetime import date
from database import initialize_database, get_connection
from payroll import calculate_salary
try:
    from payslip import generate_payslip
except ModuleNotFoundError:
    generate_payslip = None


st.set_page_config(
    page_title="Employee Payroll System",
    page_icon="💼",
    layout="wide"
)

# Initialize database
initialize_database()

# Admin login
def login():
    if st.session_state.get("authenticated", False):
        return True

    st.title("🔐 Employee Payroll Management System")
    st.write("Please sign in as an administrator.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        try:
            expected_user = st.secrets["ADMIN_USERNAME"]
            expected_pass = st.secrets["ADMIN_PASSWORD"]
        except Exception:
            st.error(
                "Admin login is not configured. "
                "Set ADMIN_USERNAME and ADMIN_PASSWORD "
                "in Streamlit Cloud → App settings → Secrets."
            )
            return False

        if (
            hmac.compare_digest(username, expected_user)
            and hmac.compare_digest(password, expected_pass)
        ):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    return False


if not login():
    st.stop()

# Sidebar navigation
st.sidebar.title("💼 Payroll Pro")
st.sidebar.caption("Employee Management System")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Employees",
        "Calculate Salary",
        "Attendance & Leave",
        "Payroll Records",
        "Reports"
    ]
)

if st.sidebar.button("🚪 Logout"):
    st.session_state["authenticated"] = False
    st.rerun()

st.title("💼 Employee Payroll Management System")
st.caption("Manage employees, salaries, attendance and payroll.")

# Create attendance table
with get_connection() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(employee_id, attendance_date)
        )
    """)

# Helper function
def get_employees(active_only=False):
    with get_connection() as conn:
        query = "SELECT * FROM employees"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name"
        return pd.read_sql_query(query, conn)

# DASHBOARD
if page == "Dashboard":
    employees = get_employees(active_only=True)

    with get_connection() as conn:
        payroll_count = conn.execute(
            "SELECT COUNT(*) FROM payroll"
        ).fetchone()[0]

        total_payroll = conn.execute(
            "SELECT COALESCE(SUM(net_salary), 0) FROM payroll"
        ).fetchone()[0]

        total_employees = conn.execute(
            "SELECT COUNT(*) FROM employees WHERE active = 1"
        ).fetchone()[0]

    a, b, c = st.columns(3)
    a.metric("👥 Active Employees", total_employees)
    b.metric("💰 Total Net Payroll", f"₹{total_payroll:,.2f}")
    c.metric("🧾 Payroll Entries", payroll_count)

    st.subheader("📊 Payroll Overview")
    with get_connection() as conn:
        monthly = pd.read_sql_query("""
            SELECT salary_month, SUM(net_salary) AS total
            FROM payroll
            GROUP BY salary_month
            ORDER BY salary_month
        """, conn)

    if not monthly.empty:
        st.bar_chart(monthly.set_index("salary_month")["total"])
    else:
        st.info("Your payroll chart will appear after you save salary records.")

    st.subheader("🕒 Recent Payroll")
    with get_connection() as conn:
        recent = pd.read_sql_query("""
            SELECT employee_id, salary_month, gross_salary,
                   deductions, net_salary
            FROM payroll
            ORDER BY id DESC LIMIT 10
        """, conn)

    if recent.empty:
        st.info("No payroll records yet.")
    else:
        st.dataframe(recent, use_container_width=True)

# EMPLOYEE MANAGEMENT
elif page == "Employees":
    st.subheader("➕ Add New Employee")

    with st.form("employee_form", clear_on_submit=True):
        employee_id = st.text_input("Employee ID *")
        name = st.text_input("Full Name *")
        department = st.text_input("Department")
        designation = st.text_input("Designation")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        joining_date = st.date_input("Joining Date", value=date.today())
        submitted = st.form_submit_button("Save Employee")

    if submitted:
        if not employee_id.strip() or not name.strip():
            st.error("Employee ID and Full Name are required.")
        else:
            try:
                with get_connection() as conn:
                    conn.execute("""
                        INSERT INTO employees
                        (employee_id, name, department, designation,
                         email, phone, joining_date, active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """, (
                        employee_id.strip(), name.strip(), department,
                        designation, email, phone, str(joining_date)
                    ))
                st.success("Employee added successfully!")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("This Employee ID already exists.")

    st.divider()
    st.subheader("🔎 Employee Directory")
    search = st.text_input("Search by ID, name or department")

    employees = get_employees()
    if search:
        mask = (
            employees["employee_id"].astype(str).str.contains(search, case=False, na=False)
            | employees["name"].astype(str).str.contains(search, case=False, na=False)
            | employees["department"].astype(str).str.contains(search, case=False, na=False)
        )
        employees = employees[mask]

    st.dataframe(employees, use_container_width=True)

    if not employees.empty:
        st.subheader("✏️ Edit Employee Details")
        selected_id = st.selectbox(
            "Choose employee ID",
            employees["employee_id"].tolist()
        )
        selected = employees[
            employees["employee_id"] == selected_id
        ].iloc[0]

        with st.form("edit_employee_form"):
            edit_name = st.text_input("Name", value=str(selected["name"] or ""))
            edit_department = st.text_input(
                "Department", value=str(selected["department"] or "")
            )
            edit_designation = st.text_input(
                "Designation", value=str(selected["designation"] or "")
            )
            edit_email = st.text_input(
                "Email", value=str(selected["email"] or "")
            )
            edit_phone = st.text_input(
                "Phone", value=str(selected["phone"] or "")
            )
            edit_active = st.checkbox(
                "Active employee",
                value=bool(selected["active"])
            )
            save_edit = st.form_submit_button("Update Employee")

        if save_edit:
            with get_connection() as conn:
                conn.execute("""
                    UPDATE employees
                    SET name=?, department=?, designation=?, email=?,
                        phone=?, active=?
                    WHERE employee_id=?
                """, (
                    edit_name, edit_department, edit_designation,
                    edit_email, edit_phone, int(edit_active), selected_id
                ))
            st.success("Employee details updated.")
            st.rerun()

# SALARY CALCULATOR
elif page == "Calculate Salary":
    st.subheader("💰 Calculate Monthly Salary")

    employees = get_employees(active_only=True)

    if employees.empty:
        st.warning("Add an employee first.")
    else:
        employee_ids = employees["employee_id"].tolist()
        selected_id = st.selectbox("Employee ID", employee_ids)
        employee = employees[
            employees["employee_id"] == selected_id
        ].iloc[0]

        with st.form("salary_form"):
            salary_month = st.text_input(
                "Salary Month (YYYY-MM)", value=date.today().strftime("%Y-%m")
            )
            basic = st.number_input("Basic Salary (₹)", min_value=0.0, step=500.0)
            allowances = st.number_input("Allowances (₹)", min_value=0.0, step=100.0)
            overtime = st.number_input("Overtime Pay (₹)", min_value=0.0, step=100.0)
            deductions = st.number_input("Deductions (₹)", min_value=0.0, step=100.0)
            calculate = st.form_submit_button("Calculate & Save Payroll")

        if calculate:
            try:
                if (
                    len(salary_month) != 7
                    or salary_month[4] != "-"
                    or not salary_month[:4].isdigit()
                    or not salary_month[5:].isdigit()
                    or not 1 <= int(salary_month[5:]) <= 12
                ):
                    raise ValueError("Enter the month as YYYY-MM, for example 2026-10.")

                salary = calculate_salary(basic, allowances, overtime, deductions)

                with get_connection() as conn:
                    conn.execute("""
                        INSERT INTO payroll
                        (employee_id, salary_month, basic_salary, allowances,
                         overtime, deductions, gross_salary, net_salary)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(employee_id, salary_month) DO UPDATE SET
                        basic_salary=excluded.basic_salary,
                        allowances=excluded.allowances,
                        overtime=excluded.overtime,
                        deductions=excluded.deductions,
                        gross_salary=excluded.gross_salary,
                        net_salary=excluded.net_salary
                    """, (
                        selected_id, salary_month, salary["basic_salary"],
                        salary["allowances"], salary["overtime"],
                        salary["deductions"], salary["gross_salary"],
                        salary["net_salary"]
                    ))

                st.success("Payroll calculated and saved!")

                x, y, z = st.columns(3)
                x.metric("Gross Salary", f"₹{salary['gross_salary']:,.2f}")
                y.metric("Deductions", f"₹{salary['deductions']:,.2f}")
                z.metric("Net Salary", f"₹{salary['net_salary']:,.2f}")

                st.session_state["last_payslip"] = {
                    "employee": {
                        "name": employee["name"],
                        "employee_id": employee["employee_id"],
                        "department": employee["department"] or "",
                        "designation": employee["designation"] or ""
                    },
                    "salary": salary,
                    "salary_month": salary_month
                }

            except (ValueError, TypeError) as error:
                st.error(str(error))

    payslip_data = st.session_state.get("last_payslip")
    if payslip_data:
        try:
            pdf = generate_payslip(
                payslip_data["employee"],
                payslip_data["salary"],
                payslip_data["salary_month"]
            )
            st.download_button(
                "📄 Download PDF Payslip",
                data=pdf,
                file_name=f"payslip_{payslip_data['employee']['employee_id']}.pdf",
                mime="application/pdf"
            )
        except Exception as error:
            st.error(f"Could not generate payslip: {error}")

# ATTENDANCE AND LEAVE
elif page == "Attendance & Leave":
    st.subheader("📅 Attendance & Leave Tracker")
    employees = get_employees(active_only=True)

    if employees.empty:
        st.warning("Add an employee first.")
    else:
        selected_id = st.selectbox(
            "Employee",
            employees["employee_id"].tolist(),
            key="attendance_employee"
        )
        attendance_date = st.date_input("Date", value=date.today())
        status = st.selectbox(
            "Status",
            ["Present", "Absent", "Leave", "Overtime"]
        )

        if st.button("Save Attendance"):
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO attendance (employee_id, attendance_date, status)
                    VALUES (?, ?, ?)
                    ON CONFLICT(employee_id, attendance_date)
                    DO UPDATE SET status=excluded.status
                """, (selected_id, str(attendance_date), status))
            st.success("Attendance saved.")

    with get_connection() as conn:
        attendance = pd.read_sql_query("""
            SELECT * FROM attendance ORDER BY attendance_date DESC
        """, conn)

    st.subheader("Attendance History")
    st.dataframe(attendance, use_container_width=True)

# PAYROLL RECORDS AND PAYSLIPS
elif page == "Payroll Records":
    st.subheader("🧾 Payroll Records")

    with get_connection() as conn:
        records = pd.read_sql_query("""
            SELECT p.*, e.name, e.department
            FROM payroll p
            LEFT JOIN employees e ON p.employee_id = e.employee_id
            ORDER BY p.id DESC
        """, conn)

    if records.empty:
        st.info("No payroll records available yet.")
    else:
        st.dataframe(records, use_container_width=True)

        chosen_record = st.selectbox(
            "Select payroll entry for PDF payslip",
            records.index.tolist(),
            format_func=lambda i: (
                f"{records.loc[i, 'name']} — "
                f"{records.loc[i, 'salary_month']}"
            )
        )

        if st.button("Prepare Selected Payslip"):
            row = records.loc[chosen_record]
            employee = {
                "name": row["name"] or "",
                "employee_id": row["employee_id"],
                "department": row["department"] or "",
                "designation": ""
            }
            salary = {
                "basic_salary": row["basic_salary"],
                "allowances": row["allowances"],
                "overtime": row["overtime"],
                "deductions": row["deductions"],
                "gross_salary": row["gross_salary"],
                "net_salary": row["net_salary"]
            }
            pdf = generate_payslip(employee, salary, row["salary_month"])
            st.download_button(
                "Download Selected PDF Payslip",
                data=pdf,
                file_name=f"payslip_{row['employee_id']}_{row['salary_month']}.pdf",
                mime="application/pdf"
            )

# REPORTS
elif page == "Reports":
    st.subheader("📈 Payroll Reports & Export")

    with get_connection() as conn:
        report = pd.read_sql_query("""
            SELECT p.employee_id, e.name, e.department, p.salary_month,
                   p.basic_salary, p.allowances, p.overtime,
                   p.deductions, p.gross_salary, p.net_salary
            FROM payroll p
            LEFT JOIN employees e ON p.employee_id = e.employee_id
            ORDER BY p.salary_month DESC
        """, conn)

    if report.empty:
        st.info("Save payroll records to generate reports.")
    else:
        st.metric("Total Net Payroll", f"₹{report['net_salary'].sum():,.2f}")
        st.dataframe(report, use_container_width=True)

        csv_data = report.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Payroll Report (CSV)",
            data=csv_data,
            file_name="payroll_report.csv",
            mime="text/csv"
        )

        by_department = report.groupby("department")["net_salary"].sum()
        st.subheader("Net Salary by Department")
        st.bar_chart(by_department)
