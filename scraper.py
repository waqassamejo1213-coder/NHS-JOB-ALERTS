"""
scraper.py — pulls job listings from NHS Jobs (jobs.nhs.uk) and saves new ones.

Selectors below were calibrated on 17 Sep 2026 against a real
https://www.jobs.nhs.uk/candidate/search/results page (view-source, not a
guess). NHS Jobs' search results use stable `data-test="search-result-*"`
attributes on each field, which are what this file selects on — these are
much less likely to break on a visual redesign than class names, but the
site can still change them. If results come back empty, re-run
`python inspect_page.py`, open the saved HTML, and check these attributes
still exist.

ETIQUETTE / LEGAL NOTES:
  - This only reads publicly visible search results — it does not log in,
    bypass any paywall, or access anything non-public.
  - Keep the polling interval reasonable (this defaults to 5 minutes) and
    set a real User-Agent identifying your tool/contact so NHS Jobs' team
    can reach you if they have concerns, rather than just blocking silently.
  - NHS Jobs' own terms and conditions (jobs.nhs.uk/candidate/acceptable-use)
    restrict use of site content to personal, non-commercial purposes, and
    require the NHS Business Services Authority's prior written agreement
    for commercial use or for reproducing/republishing content. Running
    this against jobs.nhs.uk for a commercial product — as this project
    does — is a knowing departure from those terms, a decision made by the
    project owner. This file does not constitute legal advice; if that
    changes (e.g. permission is sought/granted, or a different, licensed
    data source is used instead), update this note accordingly.
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from db import insert_job

def _clean(text: str) -> str:
    """Collapse whitespace/newlines from source-formatted HTML into single spaces."""
    return re.sub(r"\s+", " ", text or "").strip()

HEADERS = {
    # Identify yourself honestly — replace with your real contact.
    "User-Agent": "CareerProServicesJobBot/0.2 (+mailto:hello@careerproservices.co.uk)"
}

BASE_URL = "https://www.jobs.nhs.uk/candidate/search/results"

# Rough keyword -> grade inference. NHS Jobs search results don't expose a
# separate "grade" field — this pattern-matches the job title instead.
GRADE_PATTERNS = [
    ("Consultant", "Consultant"),
    ("Specialty Doctor", "Specialty Doctor"),
    ("Speciality Doctor", "Specialty Doctor"),
    ("Trust Registrar", "Trust Registrar (ST3+)"),
    ("Clinical Fellow", "Clinical Fellow"),
    ("Locally Employed Doctor", "Locally Employed Doctor"),
    ("LED", "Locally Employed Doctor"),
    ("Senior House Officer", "Senior House Officer"),
    (" SHO", "Senior House Officer"),
    ("Foundation Year 2", "FY2"),
    ("Foundation Year 1", "FY1"),
    ("Registrar", "Registrar"),
]

def infer_grade(title: str) -> str:
    lowered = title or ""
    for needle, grade in GRADE_PATTERNS:
        if needle.lower() in lowered.lower():
            return grade
    return ""

def fetch_search_page(keyword="", location="", page=1):
    params = {"keyword": keyword, "location": location, "page": page}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text

def _field_text(card, data_test):
    """Grab the <strong> value next to a 'Label: value' li, e.g. salary/closing date."""
    el = card.select_one(f'[data-test="{data_test}"]')
    if not el:
        return ""
    strong = el.find("strong")
    return _clean(strong.get_text() if strong else el.get_text())

def parse_nhs_jobs_page(html: str):
    """
    Returns a list of dicts: title, employer, location, salary, grade,
    closing_date, url, external_id.

    Card container: li.search-result
    Title + link:   [data-test="search-result-job-title"]  (an <a>)
    Employer/loc:   [data-test="search-result-location"] -> h3 text (employer)
                    plus a nested div.location-font-size (location)
    Salary:         [data-test="search-result-salary"]
    Closing date:   [data-test="search-result-closingDate"]
    """
    soup = BeautifulSoup(html, "lxml")
    jobs = []

    cards = soup.select("li.search-result")

    for card in cards:
        title_tag = card.select_one('[data-test="search-result-job-title"]')
        if not title_tag or not title_tag.get("href"):
            continue

        url = title_tag["href"]
        if url.startswith("/"):
            url = "https://www.jobs.nhs.uk" + url
        title = _clean(title_tag.get_text())
        external_id = url.rstrip("/").split("/")[-1]

        employer, location = "", ""
        loc_block = card.select_one('[data-test="search-result-location"]')
        if loc_block:
            h3 = loc_block.find("h3")
            if h3:
                loc_div = h3.find("div", class_="location-font-size")
                location = _clean(loc_div.get_text()) if loc_div else ""
                h3_copy = BeautifulSoup(str(h3), "lxml")
                nested = h3_copy.find("div", class_="location-font-size")
                if nested:
                    nested.decompose()
                employer = _clean(h3_copy.get_text())

        salary = _field_text(card, "search-result-salary")
        closing_date = _field_text(card, "search-result-closingDate")

        jobs.append({
            "source": "nhs_jobs",
            "external_id": external_id,
            "title": title,
            "employer": employer,
            "location": location,
            "salary": salary,
            "grade": infer_grade(title),
            "closing_date": closing_date,
            "url": url,
        })

    return jobs

def run_scrape_cycle(keywords, poll_delay_seconds=2):
    """
    keywords: list of search terms to sweep, e.g.
      ["psychiatry", "clinical fellow", "SHO"]
    Returns list of NEWLY discovered jobs (not seen in a previous run).
    """
    new_jobs = []
    for kw in keywords:
        try:
            html = fetch_search_page(keyword=kw)
            jobs = parse_nhs_jobs_page(html)
            for job in jobs:
                if insert_job(job):
                    new_jobs.append(job)
        except requests.RequestException as e:
            print(f"[scraper] fetch failed for '{kw}': {e}")
        time.sleep(poll_delay_seconds)  # be polite between requests
    return new_jobs

if __name__ == "__main__":
    from db import init_db
    init_db()
    found = run_scrape_cycle(["psychiatry", "clinical fellow"])
    print(f"Found {len(found)} new jobs this run.")
    for j in found:
        print(" -", j["title"], "|", j["url"])
