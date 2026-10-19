import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "payroll.db"


@contextmanager
def get_connection():
    """Open a database connection and manage transactions."""
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    """Create the required tables if they do not exist."""

    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                phone TEXT,
                department TEXT,
                designation TEXT,
                basic_salary REAL NOT NULL DEFAULT 0,
                allowances REAL NOT NULL DEFAULT 0,
                joining_date TEXT,
                username TEXT UNIQUE,
                password_hash TEXT,
                profile_photo TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS payroll (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                salary_month TEXT NOT NULL,
                basic_salary REAL NOT NULL DEFAULT 0,
                allowances REAL NOT NULL DEFAULT 0,
                overtime REAL NOT NULL DEFAULT 0,
                bonus REAL NOT NULL DEFAULT 0,
                gross_salary REAL NOT NULL DEFAULT 0,
                advance REAL NOT NULL DEFAULT 0,
                tax REAL NOT NULL DEFAULT 0,
                total_deductions REAL NOT NULL DEFAULT 0,
                net_salary REAL NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_id, salary_month),
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                attendance_date TEXT NOT NULL,
                check_in TEXT,
                check_out TEXT,
                status TEXT NOT NULL DEFAULT 'Present',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_id, attendance_date),
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS leave_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                leave_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def fetch_all(query, parameters=()):
    """Return query results as a list of dictionaries."""
    with get_connection() as conn:
        rows = conn.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]


def fetch_one(query, parameters=()):
    """Return one query result as a dictionary, or None."""
    with get_connection() as conn:
        row = conn.execute(query, parameters).fetchone()
        return dict(row) if row else None


def execute_query(query, parameters=()):
    """Execute an insert, update, or delete query."""
    with get_connection() as conn:
        cursor = conn.execute(query, parameters)
        return cursor.lastrowid


def get_employees():
    """Return all employees."""
    return fetch_all(
        "SELECT * FROM employees ORDER BY id DESC"
    )


def get_employee(employee_id):
    """Return one employee by ID."""
    return fetch_one(
        "SELECT * FROM employees WHERE id = ?",
        (employee_id,),
    )


def add_employee(
    name,
    email=None,
    phone=None,
    department=None,
    designation=None,
    basic_salary=0,
    allowances=0,
    joining_date=None,
    username=None,
    password_hash=None,
):
    """Add an employee and return the new employee ID."""

    return execute_query(
        """
        INSERT INTO employees (
            name, email, phone, department, designation,
            basic_salary, allowances, joining_date,
            username, password_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name, email, phone, department, designation,
            basic_salary, allowances, joining_date,
            username, password_hash,
        ),
    )


def update_employee(employee_id, **fields):
    """Update supported employee fields."""

    allowed_fields = {
        "name", "email", "phone", "department",
        "designation", "basic_salary", "allowances",
        "joining_date", "username", "password_hash",
        "profile_photo",
    }

    updates = {
        key: value
        for key, value in fields.items()
        if key in allowed_fields
    }

    if not updates:
        return

    assignments = ", ".join(
        f"{key} = ?" for key in updates
    )

    values = list(updates.values())
    values.append(employee_id)

    execute_query(
        f"UPDATE employees SET {assignments} WHERE id = ?",
        values,
    )


def delete_employee(employee_id):
    """Delete an employee only when no related records exist."""

    with get_connection() as conn:
        related = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM payroll WHERE employee_id = ?) +
                (SELECT COUNT(*) FROM attendance WHERE employee_id = ?) +
                (SELECT COUNT(*) FROM leave_requests WHERE employee_id = ?)
            """,
            (employee_id, employee_id, employee_id),
        ).fetchone()[0]

        if related:
            raise ValueError(
                "This employee has records. Keep the employee "
                "and deactivate them instead of deleting."
            )

        conn.execute(
            "DELETE FROM employees WHERE id = ?",
            (employee_id,),
        )


def save_payroll(
    employee_id,
    salary_month,
    basic_salary,
    allowances=0,
    overtime=0,
    bonus=0,
    gross_salary=0,
    advance=0,
    tax=0,
    total_deductions=0,
    net_salary=0,
):
    """Save a monthly payroll record."""

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO payroll (
                employee_id, salary_month, basic_salary,
                allowances, overtime, bonus, gross_salary,
                advance, tax, total_deductions, net_salary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_id, salary_month)
            DO UPDATE SET
                basic_salary = excluded.basic_salary,
                allowances = excluded.allowances,
                overtime = excluded.overtime,
                bonus = excluded.bonus,
                gross_salary = excluded.gross_salary,
                advance = excluded.advance,
                tax = excluded.tax,
                total_deductions = excluded.total_deductions,
                net_salary = excluded.net_salary
            """,
            (
                employee_id, salary_month, basic_salary,
                allowances, overtime, bonus, gross_salary,
                advance, tax, total_deductions, net_salary,
            ),
        )


def get_payroll_records(employee_id=None):
    """Return payroll records, optionally for one employee."""

    if employee_id is not None:
        return fetch_all(
            """
            SELECT p.*, e.name AS employee_name
            FROM payroll p
            JOIN employees e ON e.id = p.employee_id
            WHERE p.employee_id = ?
            ORDER BY p.salary_month DESC
            """,
            (employee_id,),
        )

    return fetch_all(
        """
        SELECT p.*, e.name AS employee_name
        FROM payroll p
        JOIN employees e ON e.id = p.employee_id
        ORDER BY p.salary_month DESC
        """
    )


def mark_attendance(
    employee_id,
    attendance_date,
    check_in=None,
    check_out=None,
    status="Present",
):
    """Create or update daily attendance."""

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO attendance (
                employee_id, attendance_date,
                check_in, check_out, status
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(employee_id, attendance_date)
            DO UPDATE SET
                check_in = COALESCE(
                    excluded.check_in, attendance.check_in
                ),
                check_out = COALESCE(
                    excluded.check_out, attendance.check_out
                ),
                status = excluded.status
            """,
            (
                employee_id, attendance_date,
                check_in, check_out, status,
            ),
        )


def get_attendance(employee_id=None):
    """Return attendance records."""

    if employee_id is not None:
        return fetch_all(
            """
            SELECT a.*, e.name AS employee_name
            FROM attendance a
            JOIN employees e ON e.id = a.employee_id
            WHERE a.employee_id = ?
            ORDER BY a.attendance_date DESC
            """,
            (employee_id,),
        )

    return fetch_all(
        """
        SELECT a.*, e.name AS employee_name
        FROM attendance a
        JOIN employees e ON e.id = a.employee_id
        ORDER BY a.attendance_date DESC
        """
    )


def add_leave_request(
    employee_id,
    leave_type,
    start_date,
    end_date,
    reason="",
):
    """Submit a leave request."""

    return execute_query(
        """
        INSERT INTO leave_requests (
            employee_id, leave_type, start_date,
            end_date, reason
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            employee_id, leave_type, start_date,
            end_date, reason,
        ),
    )


def get_leave_requests(employee_id=None):
    """Return leave requests."""

    if employee_id is not None:
        return fetch_all(
            """
            SELECT l.*, e.name AS employee_name
            FROM leave_requests l
            JOIN employees e ON e.id = l.employee_id
            WHERE l.employee_id = ?
            ORDER BY l.requested_at DESC
            """,
            (employee_id,),
        )

    return fetch_all(
        """
        SELECT l.*, e.name AS employee_name
        FROM leave_requests l
        JOIN employees e ON e.id = l.employee_id
        ORDER BY l.requested_at DESC
        """
    )


def update_leave_status(leave_id, status):
    """Approve or reject a leave request."""

    if status not in {"Pending", "Approved", "Rejected"}:
        raise ValueError("Invalid leave status.")

    execute_query(
        """
        UPDATE leave_requests
        SET status = ?, reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, leave_id),
    )


def add_audit_log(username, action, details=""):
    """Record an application action."""

    execute_query(
        """
        INSERT INTO audit_log (username, action, details)
        VALUES (?, ?, ?)
        """,
        (username, action, details),
    )


def get_audit_logs(limit=200):
    """Return recent audit records."""

    return fetch_all(
        """
        SELECT * FROM audit_log
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )


def backup_database_bytes():
    """Return a portable SQL text backup of the database."""

    with get_connection() as conn:
        statements = [
            "-- Employee Payroll database backup",
            "PRAGMA foreign_keys=OFF;",
        ]

        objects = conn.execute(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'index')
              AND name NOT LIKE 'sqlite_%'
              AND sql IS NOT NULL
            ORDER BY type, name
            """
        ).fetchall()

        for obj in objects:
            statements.append(obj["sql"] + ";")

            if obj["type"] == "table":
                table = obj["name"]
                rows = conn.execute(
                    f'SELECT * FROM "{table}"'
                ).fetchall()

                columns = [
                    column["name"]
                    for column in conn.execute(
                        f'PRAGMA table_info("{table}")'
                    ).fetchall()
                ]

                for row in rows:
                    values = []
                    for column in columns:
                        value = row[column]
                        if value is None:
                            values.append("NULL")
                        elif isinstance(value, (int, float)):
                            values.append(str(value))
                        else:
                            escaped = str(value).replace("'", "''")
                            values.append(f"'{escaped}'")

                    col_names = ", ".join(
                        f'"{column}"' for column in columns
                    )
                    statements.append(
                        f'INSERT INTO "{table}" ({col_names}) '
                        f'VALUES ({", ".join(values)});'
                    )

        statements.append("PRAGMA foreign_keys=ON;")
        return ("\n\n".join(statements) + "\n").encode("utf-8")


# Initialize the database tables when this module is imported.
init_db()
