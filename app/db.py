"""
app/db.py - the app's single door to the database.

Design rule (proposal Table 7): all database access happens in the tools
layer (app/tools/), and every tool opens its connection through here.
No other file ever writes SQL.

Simple pattern for now: open a fresh connection per call and close it.
(Localhost Postgres connects in ~1 ms, so this is plenty fast for the demo.
If we ever need more speed, we swap this for psycopg_pool - the tools
wouldn't change at all, which is exactly why the door is centralised.)
"""

import psycopg

from app.config import settings


def get_connection():
    """Open a new database connection. Use as:

        with get_connection() as conn:
            conn.execute(...)
    """
    return psycopg.connect(settings.database_url)


if __name__ == "__main__":
    # Self-test: run me from the repo root with  python -m app.db
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM applicants").fetchone()
        print(f"Connected OK. Applicants in the world: {row[0]}")