r"""
app/tools/loans.py - safe, read-only tools for loan questions.

A "tool" is the only unit allowed to talk to the database (always via a
connection from app/db.py). Rules for every tool we will ever write:

1. Parameterised queries ONLY - never build SQL with f-strings. The %s
   placeholders are filled by the database driver, which makes SQL
   injection structurally impossible.
2. Return plain Python dicts (or None) - never raw DB rows. Whatever
   calls a tool stays decoupled from the database.
3. Unknown record -> return None. The pipeline later turns None into
   the honest answer: "I could not find it." (spec: never fabricate)
4. Note what is NOT here: pan_number is never even selected. Least
   privilege starts at the tool, before any permission gate runs.
"""

from app.db import get_connection


def get_loan_status(loan_id: str):
    """Return everything known about one loan, or None if it does not exist."""
    with get_connection() as conn:
        # --- query 1: the loan + its applicant (join, still parameterised) ---
        loan_row = conn.execute(
            """
            SELECT l.loan_id, l.loan_amount, l.emi_amount, l.tenure_months,
                   l.status, l.disbursed_date,
                   a.applicant_id, a.full_name, a.employer,
                   a.monthly_income, a.kyc_verified
            FROM loans l
            JOIN applicants a ON a.applicant_id = l.applicant_id
            WHERE l.loan_id = %s
            """,
            (loan_id,),
        ).fetchone()

        if loan_row is None:
            return None  # honest 'not found'

        # --- query 2: the repayment history, oldest first ---
        repay_rows = conn.execute(
            """
            SELECT record_id, due_date, paid_date, amount, status
            FROM repayments
            WHERE loan_id = %s
            ORDER BY due_date
            """,
            (loan_id,),
        ).fetchall()

    repayments = [
        {
            "record_id": r[0],
            "due_date": str(r[1]),
            "paid_date": str(r[2]) if r[2] else None,
            "amount": float(r[3]),
            "status": r[4],
        }
        for r in repay_rows
    ]

    # The spec wants missed EMIs WITH their dates - computed from real rows.
    missed_dates = [r["due_date"] for r in repayments if r["status"] == "missed"]

    (
        loan_id_, loan_amount, emi_amount, tenure_months, status, disbursed,
        applicant_id, full_name, employer, monthly_income, kyc_verified,
    ) = loan_row

    return {
        "loan": {
            "loan_id": loan_id_,
            "loan_amount": float(loan_amount),
            "emi_amount": float(emi_amount),
            "tenure_months": tenure_months,
            "status": status,
            "disbursed_date": str(disbursed),
        },
        "applicant": {
            "applicant_id": applicant_id,
            "full_name": full_name,
            "employer": employer,
            "monthly_income": float(monthly_income) if monthly_income else None,
            "kyc_verified": kyc_verified,
        },
        "repayments": repayments,
        "missed_emis": {
            "count": len(missed_dates),
            "dates": missed_dates,
        },
    }


if __name__ == "__main__":
    # Self-test: run from the repo root with  python -m app.tools.loans
    import json

    result = get_loan_status("LN-1025")

    assert result is not None, "LN-1025 must exist in the seeded world"
    assert result["missed_emis"]["count"] == 3, result["missed_emis"]
    assert result["missed_emis"]["dates"] == ["2026-06-05", "2026-08-05", "2026-10-05"]
    assert get_loan_status("LN-9999") is None, "unknown loan must return None"

    print(json.dumps(result, indent=2))
    print("\nSelf-checks passed: 3 missed EMIs with dates; unknown loan -> None.")