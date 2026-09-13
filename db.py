"""
db.py — SQLite storage for scraped jobs and saved user filters.

Keeping this as plain SQLite (no server needed) so the whole project
can run on a single small VPS or even a Raspberry Pi to start.
"""
import sqlite3
from contextlib import contextmanager

DB_PATH = "jobs.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,           -- 'nhs_jobs', 'trac', 'nhs_scotland', 'hscni'
                external_id TEXT NOT NULL,      -- id/slug from the source site
                title TEXT,
                employer TEXT,
                location TEXT,
                salary TEXT,
                grade TEXT,
                closing_date TEXT,
                url TEXT,
                first_seen TEXT DEFAULT (datetime('now')),
                UNIQUE(source, external_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                keyword TEXT,                   -- e.g. "psychiatry", "clinical fellow"
                location TEXT,                  -- e.g. "London"
                grade TEXT,                     -- e.g. "consultant", "band 6"
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filter_id INTEGER,
                job_id INTEGER,
                sent_at TEXT DEFAULT (datetime('now')),
                UNIQUE(filter_id, job_id)
            )
        """)


def insert_job(job: dict) -> bool:
    """Returns True if this was a NEW job (not seen before)."""
    with get_conn() as conn:
        try:
            conn.execute(
                """INSERT INTO jobs (source, external_id, title, employer, location,
                   salary, grade, closing_date, url)
                   VALUES (:source, :external_id, :title, :employer, :location,
                   :salary, :grade, :closing_date, :url)""",
                job,
            )
            return True
        except sqlite3.IntegrityError:
            return False  # already exists


def get_new_jobs_since(job_ids_already_alerted):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY first_seen DESC LIMIT 500").fetchall()
        return [dict(r) for r in rows if r["id"] not in job_ids_already_alerted]


def get_active_filters():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM filters WHERE active = 1").fetchall()
        return [dict(r) for r in rows]


def add_filter(email, keyword="", location="", grade=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO filters (email, keyword, location, grade) VALUES (?, ?, ?, ?)",
            (email, keyword, location, grade),
        )


def mark_alert_sent(filter_id, job_id):
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO alerts_sent (filter_id, job_id) VALUES (?, ?)",
                (filter_id, job_id),
            )
        except sqlite3.IntegrityError:
            pass  # already alerted this filter for this job


def already_alerted(filter_id, job_id) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM alerts_sent WHERE filter_id = ? AND job_id = ?",
            (filter_id, job_id),
        ).fetchone()
        return row is not None


def get_recent_jobs(limit=50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY first_seen DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
