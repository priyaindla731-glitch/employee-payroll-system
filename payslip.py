from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def generate_payslip(employee, payroll):
    """Generate a PDF salary slip and return its bytes."""

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    content = []

    content.append(
        Paragraph("EMPLOYEE PAYSLIP", styles["Title"])
    )
    content.append(Spacer(1, 20))

    employee_name = employee.get("name", "Employee")
    employee_id = employee.get("id", "")
    department = employee.get("department", "")
    month = payroll.get("salary_month", payroll.get("month", ""))

    content.append(
        Paragraph(f"<b>Employee:</b> {employee_name}", styles["Normal"])
    )
    content.append(
        Paragraph(f"<b>Employee ID:</b> {employee_id}", styles["Normal"])
    )
    content.append(
        Paragraph(f"<b>Department:</b> {department}", styles["Normal"])
    )
    content.append(
        Paragraph(f"<b>Salary Month:</b> {month}", styles["Normal"])
    )
    content.append(Spacer(1, 20))

    rows = [
        ["Salary Description", "Amount"],
        ["Basic Salary", payroll.get("basic_salary", 0)],
        ["Allowances", payroll.get("allowances", 0)],
        ["Overtime", payroll.get("overtime", 0)],
        ["Bonus", payroll.get("bonus", 0)],
        ["Gross Salary", payroll.get("gross_salary", 0)],
        ["Advance Deduction", payroll.get("advance", 0)],
        ["Tax Deduction", payroll.get("tax", 0)],
        ["Total Deductions", payroll.get("total_deductions", 0)],
        ["NET SALARY", payroll.get("net_salary", 0)],
    ]

    table = Table(rows, colWidths=[300, 150])

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#253858")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8EAF6")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 8),
        ])
    )

    content.append(table)
    content.append(Spacer(1, 25))
    content.append(
        Paragraph(
            "This is a computer-generated salary slip.",
            styles["Normal"],
        )
    )

    doc.build(content)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
