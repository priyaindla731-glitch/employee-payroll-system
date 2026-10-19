import sqlite3

DB_NAME = "payroll.db"


def get_connection():
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                department TEXT,
                designation TEXT,
                email TEXT,
                phone TEXT,
                joining_date TEXT,
                active INTEGER DEFAULT 1
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS payroll (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT NOT NULL,
                salary_month TEXT NOT NULL,
                basic_salary REAL NOT NULL,
                allowances REAL DEFAULT 0,
                overtime REAL DEFAULT 0,
                deductions REAL DEFAULT 0,
                gross_salary REAL NOT NULL,
                net_salary REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_id, salary_month)
            )
        """)
