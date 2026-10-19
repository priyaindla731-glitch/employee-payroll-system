import streamlit as st
import csv
import io
from datetime import date

st.set_page_config(
    page_title="Employee Payroll System",
    page_icon="💼",
    layout="wide"
)

# Temporary session storage
if "employees" not in st.session_state:
    st.session_state.employees = []

st.title("💼 Employee Payroll Management System")
st.caption("Manage employee details and calculate monthly salaries.")

# Dashboard
total_employees = len(st.session_state.employees)
total_payroll = sum(
    emp["net_salary"] for emp in st.session_state.employees
)

c1, c2 = st.columns(2)
c1.metric("Total Employees", total_employees)
c2.metric("Total Monthly Payroll", f"₹{total_payroll:,.2f}")

st.divider()

tab1, tab2, tab3 = st.tabs(
    ["➕ Add Employee", "👥 Employee Records", "🧾 Payslip"]
)

with tab1:
    st.subheader("Employee and Salary Details")

    with st.form("employee_form"):
        name = st.text_input("Employee Name")
        emp_id = st.text_input("Employee ID")
        department = st.text_input("Department")
        month = st.selectbox(
            "Salary Month",
            ["January", "February", "March", "April", "May",
             "June", "July", "August", "September", "October",
             "November", "December"]
        )
        basic = st.number_input("Basic Salary (₹)", min_value=0.0)
        allowances = st.number_input("Allowances (₹)", min_value=0.0)
        deductions = st.number_input("Deductions (₹)", min_value=0.0)

        submitted = st.form_submit_button("Calculate and Save")

    if submitted:
        if not name.strip() or not emp_id.strip():
            st.error("Enter employee name and employee ID.")
        elif any(
            e["emp_id"].lower() == emp_id.strip().lower()
            for e in st.session_state.employees
        ):
            st.error("This employee ID already exists.")
        elif deductions > basic + allowances:
            st.error("Deductions cannot exceed gross salary.")
        else:
            gross = basic + allowances
            net = gross - deductions

            employee = {
                "name": name.strip(),
                "emp_id": emp_id.strip(),
                "department": department.strip(),
                "month": month,
                "date": str(date.today()),
                "basic": basic,
                "allowances": allowances,
                "deductions": deductions,
                "gross_salary": gross,
                "net_salary": net
            }

            st.session_state.employees.append(employee)
            st.success("Employee payroll record added!")
            st.rerun()

with tab2:
    st.subheader("Employee Records")

    if st.session_state.employees:
        search = st.text_input("Search by name or employee ID")
        records = [
            e for e in st.session_state.employees
            if search.lower() in e["name"].lower()
            or search.lower() in e["emp_id"].lower()
        ]

        st.dataframe(records, use_container_width=True)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=records[0].keys()) if records else None
        if writer:
            writer.writeheader()
            writer.writerows(records)

            st.download_button(
                "Download Employee Records (CSV)",
                output.getvalue(),
                file_name="employee_payroll_records.csv",
                mime="text/csv"
            )
    else:
        st.info("No employee records yet. Add an employee first.")

with tab3:
    st.subheader("Generate Payslip")

    if st.session_state.employees:
        choices = {
            f'{e["name"]} — {e["emp_id"]} — {e["month"]}': e
            for e in st.session_state.employees
        }

        selected = st.selectbox("Choose employee", list(choices.keys()))
        e = choices[selected]

        st.write(f"**Employee:** {e['name']}")
        st.write(f"**Employee ID:** {e['emp_id']}")
        st.write(f"**Department:** {e['department']}")
        st.write(f"**Salary Month:** {e['month']}")
        st.write(f"**Basic Salary:** ₹{e['basic']:,.2f}")
        st.write(f"**Allowances:** ₹{e['allowances']:,.2f}")
        st.write(f"**Gross Salary:** ₹{e['gross_salary']:,.2f}")
        st.write(f"**Deductions:** ₹{e['deductions']:,.2f}")
        st.subheader(f"Net Salary: ₹{e['net_salary']:,.2f}")

        payslip = f"""EMPLOYEE PAYSLIP
Employee: {e['name']}
Employee ID: {e['emp_id']}
Department: {e['department']}
Salary Month: {e['month']}
Basic Salary: Rs. {e['basic']:.2f}
Allowances: Rs. {e['allowances']:.2f}
Gross Salary: Rs. {e['gross_salary']:.2f}
Deductions: Rs. {e['deductions']:.2f}
Net Salary: Rs. {e['net_salary']:.2f}
"""
        st.download_button(
            "Download Payslip",
            payslip,
            file_name=f"payslip_{e['emp_id']}.txt",
            mime="text/plain"
        )
    else:
        st.info("Add an employee before generating a payslip.")
