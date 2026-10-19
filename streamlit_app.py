import streamlit as st

st.set_page_config(
    page_title="Employee Payroll System",
    page_icon="💼",
    layout="wide"
)

st.title("💼 Employee Payroll Management System")
st.write("Calculate employee salaries easily.")

st.header("Employee Details")

name = st.text_input("Employee Name")
employee_id = st.text_input("Employee ID")
department = st.text_input("Department")

st.header("Salary Details")

basic = st.number_input("Basic Salary (₹)", min_value=0.0)
allowances = st.number_input("Allowances (₹)", min_value=0.0)
deductions = st.number_input("Deductions (₹)", min_value=0.0)

if st.button("Calculate Salary"):
    if not name.strip() or not employee_id.strip():
        st.error("Please enter the employee name and ID.")
    elif deductions > basic + allowances:
        st.error("Deductions cannot exceed gross salary.")
    else:
        gross = basic + allowances
        net = gross - deductions

        st.success("Salary calculated successfully!")
        st.write("Employee:", name)
        st.write("Employee ID:", employee_id)
        st.write("Department:", department)
        st.metric("Gross Salary", f"₹{gross:,.2f}")
        st.metric("Net Salary", f"₹{net:,.2f}")
