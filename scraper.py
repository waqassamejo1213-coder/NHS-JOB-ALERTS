"""
scraper.py — pulls job listings from NHS Jobs (jobs.nhs.uk) and saves new ones.

IMPORTANT — READ THIS FIRST:
I built this without live internet access, so the CSS selectors below are
my best estimate based on the site's known structure (GOV.UK-style server-
rendered HTML, listings showing salary/closing date/contract type per card).
Websites change their markup often. Before relying on this:

  1. Run `python inspect_page.py` (included) to save a real search results
     page to disk.
  2. Open it and confirm the selectors in `parse_nhs_jobs_page()` below still
     match — right-click a job card in your browser, "Inspect", and compare.
  3. Adjust the CSS selectors as needed. This is normal — every scraper needs
     this calibration step and needs occasional re-calibration when the site
     redesigns.

ETIQUETTE / LEGAL NOTES:
  - This only reads publicly visible search results — it does not log in,
    bypass any paywall, or access anything non-public.
  - Keep the polling interval reasonable (this defaults to 5 minutes) and
    set a real User-Agent identifying your tool/contact so NHS Jobs' team
    can reach you if they have concerns, rather than just blocking silently.
  - Check https://www.jobs.nhs.uk/terms-and-conditions (and the equivalent
    for Trac, NHS Scotland, HSCNI) for their current scraping/automated
    access policy before running this against their live site continuously.
    Policies change; this file does not constitute legal advice.
"""
import time
import requests
from bs4 import BeautifulSoup
from db import insert_job

HEADERS = {
    # Identify yourself honestly — replace with your real contact.
    "User-Agent": "CareerProServicesJobBot/0.1 (+mailto:hello@careerproservices.co.uk)"
}

BASE_URL = "https://www.jobs.nhs.uk/candidate/search/results"


def fetch_search_page(keyword="", location="", page=1):
    params = {"keyword": keyword, "location": location, "page": page}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def parse_nhs_jobs_page(html: str):
    """
    Returns a list of dicts: title, employer, location, salary, grade,
    closing_date, url, external_id.

    NOTE: selectors are placeholders — verify against real HTML (see
    module docstring). NHS Jobs listing cards have historically used
    <li> or <div> elements with a job title link, plus definition-list-
    style metadata (salary, closing date, contract type).
    """
    soup = BeautifulSoup(html, "lxml")
    jobs = []

    # Placeholder selector — adjust after inspecting real markup.
    cards = soup.select("li.nhsuk-list-panel, div.search-result, li.search-result")

    for card in cards:
        link_tag = card.select_one("a")
        if not link_tag or not link_tag.get("href"):
            continue

        url = link_tag["href"]
        if url.startswith("/"):
            url = "https://www.jobs.nhs.uk" + url

        title = link_tag.get_text(strip=True)
        external_id = url.rstrip("/").split("/")[-1]

        text_blob = card.get_text(" ", strip=True)

        def extract_after(label):
            if label in text_blob:
                after = text_blob.split(label, 1)[1]
                return after.split("·")[0].strip()[:120]
            return ""

        jobs.append({
            "source": "nhs_jobs",
            "external_id": external_id,
            "title": title,
            "employer": extract_after("Employer:") or "",
            "location": extract_after("Location:") or "",
            "salary": extract_after("Salary:"),
            "grade": "",
            "closing_date": extract_after("Closing date:"),
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
