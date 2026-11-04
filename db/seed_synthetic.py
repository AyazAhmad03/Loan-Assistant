r"""
Phase 1 - Step 3: load the synthetic world into Postgres.

Run from the repo root (Windows PowerShell):
    python .\db\seed_synthetic.py

The script is re-runnable: it wipes the tables (TRUNCATE) and inserts
everything again, so you always end up with the exact same synthetic world.
At the end it re-reads the database and verifies every planned edge case,
so you know the data is correct before we build anything on top of it.
"""

import os
from pathlib import Path

import psycopg


# --- tiny .env reader so the script finds DATABASE_URL without extra libraries ---
def load_dotenv() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


load_dotenv()
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://loan:loan@localhost:5432/loan_assistant"
)

# ---------------------------------------------------------------------------
# The synthetic world - every row is fictional (proposal section 5.5).
# ---------------------------------------------------------------------------

# (applicant_id, full_name, pan_number, employer, monthly_income, kyc_verified)
# None = a deliberately missing field -> becomes a refusal-path test later.
APPLICANTS = [
    ("AP-1001", "Rahul Sharma", "ABCDE1234F", "Tata Consultancy", 45000, True),
    ("AP-1002", "Rahul Sharma", "BCDEA2345G", "Infosys", 62000, True),  # twin name -> disambiguation test
    ("AP-1003", "Rahul Verma", "CDEAB3456H", "Wipro", 39000, True),
    ("AP-1004", "Priya Nair", None, "HDFC Bank", None, False),  # missing PAN + income -> refusal test
]

# (loan_id, applicant_id, loan_amount, emi_amount, tenure_months, status, disbursed_date)
LOANS = [
    ("LN-1025", "AP-1001", 500000, 11800, 48, "active", "2025-11-05"),
    ("LN-2048", "AP-1002", 800000, 19200, 60, "active", "2025-08-10"),
    ("LN-3091", "AP-1003", 300000, 7100, 48, "active", "2026-01-20"),
    ("LN-4102", "AP-1004", 250000, 5900, 60, "active", "2025-12-01"),
]

# LN-1025 is the golden example: EMI due on the 5th of each month,
# missed June, August and October 2026 = exactly 3 missed EMIs.
REPAY_1025 = [
    ("PAY-201", "2026-06-05", None, 11800, "missed"),
    ("PAY-202", "2026-07-05", "2026-07-03", 11800, "paid"),
    ("PAY-203", "2026-08-05", None, 11800, "missed"),
    ("PAY-204", "2026-09-05", "2026-09-04", 11800, "paid"),
    ("PAY-205", "2026-10-05", None, 11800, "missed"),
]

# LN-2048 is a clean payer (contrast case), LN-3091 is sporadic.
REPAY_OTHERS = [
    ("PAY-301", "LN-2048", "2026-06-10", "2026-06-09", 19200, "paid"),
    ("PAY-302", "LN-2048", "2026-07-10", "2026-07-08", 19200, "paid"),
    ("PAY-303", "LN-2048", "2026-08-10", "2026-08-09", 19200, "paid"),
    ("PAY-901", "LN-3091", "2026-08-20", None, 7100, "missed"),
    ("PAY-902", "LN-3091", "2026-09-20", "2026-09-22", 7100, "paid"),
]

# Who may see which field. support_agent must NEVER see PAN or income.
PERMISSIONS = [
    ("credit_manager", "applicants", "pan_number", True),
    ("credit_manager", "applicants", "monthly_income", True),
    ("support_agent", "applicants", "pan_number", False),  # must be denied/masked
    ("support_agent", "applicants", "monthly_income", False),
    ("support_agent", "applicants", "full_name", True),
    ("support_agent", "repayments", "status", True),
]


def seed() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        cur = conn.cursor()

        # Wipe everything so the script can be re-run safely.
        cur.execute(
            "TRUNCATE audit_logs, repayments, loans, applicants, role_field_permissions CASCADE"
        )

        cur.executemany(
            "INSERT INTO applicants VALUES (%s, %s, %s, %s, %s, %s)", APPLICANTS
        )
        cur.executemany(
            "INSERT INTO loans VALUES (%s, %s, %s, %s, %s, %s, %s)", LOANS
        )
        cur.executemany(
            """INSERT INTO repayments (record_id, loan_id, due_date, paid_date, amount, status)
               VALUES (%s, 'LN-1025', %s, %s, %s, %s)""",
            REPAY_1025,
        )
        cur.executemany(
            """INSERT INTO repayments (record_id, loan_id, due_date, paid_date, amount, status)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            REPAY_OTHERS,
        )
        cur.executemany(
            "INSERT INTO role_field_permissions VALUES (%s, %s, %s, %s)", PERMISSIONS
        )

        # 8 more ordinary customers so the world has realistic volume
        # (the proposal wants a 10-20 customer demo set).
        for i in range(8):
            n = i + 5  # n = 5 .. 12
            cur.execute(
                "INSERT INTO applicants VALUES (%s, %s, %s, %s, %s, TRUE)",
                (
                    f"AP-10{n:02d}",
                    f"Customer {n}",
                    f"AAAPA{n:04d}F",
                    "Reliance",
                    30000 + n * 1000,
                ),
            )
            cur.execute(
                "INSERT INTO loans VALUES (%s, %s, %s, %s, %s, 'active', '2026-01-10')",
                (
                    f"LN-50{i + 1:02d}",
                    f"AP-10{n:02d}",
                    200000 + n * 25000,
                    5000 + n * 200,
                    36,
                ),
            )

        verify(cur)
        # If verify() above raised an error, the `with` block rolls everything
        # back - so a failed seed never leaves half-written data behind.


def verify(cur) -> None:
    """Re-read the database and prove every planned edge case is really there."""
    cur.execute("SELECT COUNT(*) FROM applicants")
    n_applicants = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM loans")
    n_loans = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM repayments")
    n_repayments = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM role_field_permissions")
    n_permissions = cur.fetchone()[0]

    # The golden example: LN-1025 must show exactly 3 missed EMIs since June 2026.
    cur.execute(
        "SELECT COUNT(*) FROM repayments "
        "WHERE loan_id = 'LN-1025' AND status = 'missed' AND due_date >= '2026-06-01'"
    )
    missed_1025 = cur.fetchone()[0]

    # Disambiguation test: two DIFFERENT people named 'Rahul Sharma'.
    cur.execute(
        "SELECT COUNT(DISTINCT applicant_id) FROM applicants WHERE full_name = 'Rahul Sharma'"
    )
    rahuls = cur.fetchone()[0]

    # Refusal test: Priya Nair owns a loan but has no PAN and no income on file.
    cur.execute(
        "SELECT a.pan_number, a.monthly_income FROM applicants a "
        "JOIN loans l ON l.applicant_id = a.applicant_id "
        "WHERE a.full_name = 'Priya Nair'"
    )
    priya_pan, priya_income = cur.fetchone()

    checks = [
        ("applicants", n_applicants, 12),
        ("loans", n_loans, 12),
        ("repayments", n_repayments, 10),
        ("permission rows", n_permissions, 6),
        ("missed EMIs on LN-1025 (the golden number)", missed_1025, 3),
        ("different customers named 'Rahul Sharma'", rahuls, 2),
        ("Priya Nair PAN is missing", priya_pan, None),
        ("Priya Nair income is missing", priya_income, None),
    ]

    print("\n--- self-check ---")
    failed = False
    for label, got, expected in checks:
        ok = got == expected
        failed = failed or not ok
        print(f"{'OK  ' if ok else 'FAIL'} {label}: got {got}, expected {expected}")

    if failed:
        raise SystemExit("\nSeed data does not match the plan - fix before continuing.")
    print("\nAll checks passed. The synthetic world is ready.")


if __name__ == "__main__":
    seed()