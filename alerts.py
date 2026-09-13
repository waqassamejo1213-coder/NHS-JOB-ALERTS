"""
alerts.py — checks newly scraped jobs against saved filters and emails matches.

Uses plain SMTP so you can plug in any provider (Gmail app password,
SendGrid, Postmark, your own mail server). Set credentials via
environment variables — never hardcode them.

Required env vars (put these in a .env file, see .env.example):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_FROM_EMAIL
"""
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from db import get_recent_jobs, get_active_filters, already_alerted, mark_alert_sent

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL", SMTP_USER)


def job_matches_filter(job: dict, f: dict) -> bool:
    def contains(haystack, needle):
        if not needle:
            return True  # empty filter field = don't restrict on it
        return needle.lower() in (haystack or "").lower()

    return (
        contains(job["title"], f["keyword"])
        and contains(job["location"], f["location"])
        and contains(job["grade"] or job["title"], f["grade"])
    )


def send_email(to_email: str, subject: str, body: str):
    if not SMTP_HOST:
        print(f"[alerts] SMTP not configured — would have sent to {to_email}: {subject}")
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, [to_email], msg.as_string())


def run_alert_cycle():
    jobs = get_recent_jobs(limit=200)
    filters = get_active_filters()
    sent_count = 0

    for f in filters:
        matches = [j for j in jobs if job_matches_filter(j, f) and not already_alerted(f["id"], j["id"])]
        if not matches:
            continue

        lines = [f"{j['title']} — {j['employer']} ({j['location']})\n{j['url']}\n" for j in matches]
        body = (
            f"New NHS job matches for your saved filter "
            f"(keyword='{f['keyword']}', location='{f['location']}', grade='{f['grade']}'):\n\n"
            + "\n".join(lines)
        )
        send_email(f["email"], f"{len(matches)} new NHS job match(es)", body)

        for j in matches:
            mark_alert_sent(f["id"], j["id"])
        sent_count += len(matches)

    return sent_count


if __name__ == "__main__":
    n = run_alert_cycle()
    print(f"Sent {n} alert email(s).")
