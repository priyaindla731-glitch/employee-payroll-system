def calculate_salary(
    basic_salary,
    allowances=0,
    overtime=0,
    bonus=0,
    advance=0,
    tax=0,
):
    """Calculate gross salary, deductions, and net salary."""

    values = {
        "Basic salary": basic_salary,
        "Allowances": allowances,
        "Overtime": overtime,
        "Bonus": bonus,
        "Advance deduction": advance,
        "Tax deduction": tax,
    }

    for name, value in values.items():
        if value < 0:
            raise ValueError(f"{name} cannot be negative.")

    gross_salary = (
        basic_salary + allowances + overtime + bonus
    )

    total_deductions = advance + tax

    if total_deductions > gross_salary:
        raise ValueError(
            "Total deductions cannot exceed gross salary."
        )

    net_salary = gross_salary - total_deductions

    return {
        "basic_salary": basic_salary,
        "allowances": allowances,
        "overtime": overtime,
        "bonus": bonus,
        "gross_salary": gross_salary,
        "advance": advance,
        "tax": tax,
        "total_deductions": total_deductions,
        "net_salary": net_salary,
    }
