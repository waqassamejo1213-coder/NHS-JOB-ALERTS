"""
inspect_page.py — run this FIRST on your own machine (with internet).

It saves the raw HTML of a real NHS Jobs search results page to
`sample_page.html` so you can open it in a text editor / browser devtools
and confirm the CSS selectors used in scraper.py actually match.

Usage:
    python inspect_page.py "psychiatry"
"""
import sys
from scraper import fetch_search_page

if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "psychiatry"
    html = fetch_search_page(keyword=keyword)
    with open("sample_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved {len(html)} characters to sample_page.html")
    print("Open it in a browser or editor, then compare against the")
    print("selectors in parse_nhs_jobs_page() in scraper.py.")
