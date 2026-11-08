"""
app/main.py - the FastAPI application.

Phase 2 scope: expose the tools over HTTP so any app (LOS/CRM later) can
call them. There is NO LLM here and NO real intent understanding yet -
/ask simply grabs the loan ID out of the question and calls the tool.
The full pipeline (intent -> entity -> permission -> tools -> answer)
comes later; this endpoint only proves the plumbing works end to end.
"""

import re

from fastapi import FastAPI

from app.db import get_connection
from app.tools.loan_status import get_loan_status

app = FastAPI(title="Loan Assistant (Module 2)", version="0.1.0")

# Phase-2-dumb "entity resolution": find a loan ID like LN-1025 in the text.
LOAN_ID_PATTERN = re.compile(r"LN-\d+", re.IGNORECASE)


@app.get("/health")
def health():
    """Proves the app is up AND the database is reachable."""
    with get_connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "database": "reachable"}


@app.get("/ask")
def ask(question: str):
    """Take a plain-English question, return a grounded answer.

    Honest failures return 200 with an 'I could not find...' message -
    the question was processed fine; the HONEST ANSWER is 'not found'.
    """
    match = LOAN_ID_PATTERN.search(question)
    if match is None:
        return {
            "question": question,
            "answer": "I could not find a loan ID in your question.",
            "data": None,
            "sources": [],
        }

    loan_id = match.group(0).upper()
    result = get_loan_status(loan_id)

    if result is None:
        return {
            "question": question,
            "answer": f"I could not find loan {loan_id}.",
            "data": None,
            "sources": [],
        }

    missed = result["missed_emis"]
    dates = ", ".join(missed["dates"]) if missed["dates"] else "none on record"

    summary = (
        f"Loan {loan_id} is {result['loan']['status']} "
        f"({result['applicant']['full_name']}, {result['applicant']['employer']}). "
        f"Missed EMIs: {missed['count']} ({dates}). "
        f"EMI amount: {result['loan']['emi_amount']:.0f}."
    )

    return {
        "question": question,
        "answer": summary,
        "data": result,
        "sources": [r["record_id"] for r in result["repayments"]],
    }