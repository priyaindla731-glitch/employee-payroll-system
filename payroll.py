def calculate_salary(
    basic_salary,
    allowances=0,
    overtime=0,
    deductions=0
):
    values = [basic_salary, allowances, overtime, deductions]

    if any(value < 0 for value in values):
        raise ValueError("Salary amounts cannot be negative.")

    gross_salary = basic_salary + allowances + overtime

    if deductions > gross_salary:
        raise ValueError("Deductions cannot exceed gross salary.")

    net_salary = gross_salary - deductions

    return {
        "basic_salary": round(basic_salary, 2),
        "allowances": round(allowances, 2),
        "overtime": round(overtime, 2),
        "deductions": round(deductions, 2),
        "gross_salary": round(gross_salary, 2),
        "net_salary": round(net_salary, 2)
    }
