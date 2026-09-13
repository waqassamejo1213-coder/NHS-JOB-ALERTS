"""
app.py — Flask backend for the combined PWA (job alerts + AI statement writer).

Routes:
    GET  /                     -> the app shell (index.html)
    GET  /static/<path>        -> manifest, service worker, icons
    GET  /api/jobs             -> JSON list of recently scraped jobs
    POST /api/alerts           -> save a new email alert filter
    POST /api/draft-statement  -> proxies to the Anthropic API server-side
                                   (keeps your API key private — never sent
                                   to the browser)

Run:
    cp .env.example .env          # fill in ANTHROPIC_API_KEY and SMTP details
    pip install -r requirements.txt
    flask --app app run --debug
"""
import os
import requests
from flask import Flask, jsonify, request, send_from_directory, render_template
from dotenv import load_dotenv
from db import init_db, get_recent_jobs, add_filter

load_dotenv()

app = Flask(__name__)
init_db()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


@app.route("/api/jobs")
def api_jobs():
    jobs = get_recent_jobs(limit=100)
    return jsonify(jobs)


@app.route("/api/alerts", methods=["POST"])
def api_alerts():
    data = request.get_json(force=True) or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "email is required"}), 400

    add_filter(
        email=email,
        keyword=data.get("keyword", "").strip(),
        location=data.get("location", "").strip(),
        grade=data.get("grade", "").strip(),
    )
    return jsonify({"status": "ok"})


@app.route("/api/draft-statement", methods=["POST"])
def api_draft_statement():
    if not ANTHROPIC_API_KEY:
        return jsonify({
            "error": "Server is not configured with an ANTHROPIC_API_KEY. "
                     "Add one to your .env file (see .env.example)."
        }), 500

    data = request.get_json(force=True) or {}
    advert = (data.get("advert") or "").strip()
    spec = (data.get("spec") or "").strip()
    tracapp = (data.get("tracapp") or "").strip()
    experience = (data.get("experience") or "").strip()
    length = (data.get("length") or "").strip()
    tone = (data.get("tone") or "").strip()

    if not advert or not (experience or tracapp):
        return jsonify({"error": "Please provide the job advert plus your Trac application or experience notes."}), 400

    prompt = f"""You are helping a doctor draft a supporting statement for an NHS job application.

JOB ADVERT / JOB DESCRIPTION:
{advert}

PERSON SPECIFICATION:
{spec or '(not provided — infer likely criteria from the advert)'}

CANDIDATE'S TRAC APPLICATION CONTENT (work history, training, qualifications, as already entered on their application — treat this as accurate, specific source material):
{tracapp or '(not provided)'}

ADDITIONAL NOTES FROM THE CANDIDATE:
{experience or '(none provided)'}

CONSTRAINTS:
{'- Target length: ' + length if length else '- Aim for roughly 400-600 words unless the advert suggests otherwise.'}
{'- Tone: ' + tone if tone else '- Tone: professional, direct, confident, no clichés.'}

Write a tailored supporting statement that:
- Directly addresses the essential and desirable criteria in the person specification, using the candidate's real, specific experience from the Trac application content and notes above — not invented details
- Prioritises concrete examples (cases, audits, procedures, outcomes) over vague claims
- Reads naturally, not like a template with slots filled in
- Does not fabricate any experience, qualification, or outcome not mentioned in the source material
- Ends with a brief, genuine statement of interest in this specific role and trust

Output ONLY the supporting statement text, no preamble or notes."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        text_blocks = [b["text"] for b in result.get("content", []) if b.get("type") == "text"]
        draft = "\n".join(text_blocks).strip()
        if not draft:
            return jsonify({"error": "No draft returned by the model."}), 502
        return jsonify({"draft": draft})
    except requests.RequestException as e:
        return jsonify({"error": f"AI request failed: {e}"}), 502


if __name__ == "__main__":
    app.run(debug=True)
