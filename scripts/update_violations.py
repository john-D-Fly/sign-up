#!/usr/bin/env python3
"""
Download Dedrone’s Drone-Violations table and emit data/violations.json
Run manually or from GitHub Actions.
"""

import json, os, requests
from bs4 import BeautifulSoup

URL  = "https://www.dedrone.com/drone-violations-database"
OUT  = os.path.join("data", "violations.json")

def scrape() -> list[dict]:
    html = requests.get(URL, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    rows = []
    for tr in soup.select("table tbody tr"):
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cols) >= 3:
            rows.append({"date": cols[0], "location": cols[1], "summary": cols[2]})
    return rows

def main():
    records = scrape()
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"Wrote {len(records)} rows → {OUT}")

if __name__ == "__main__":
    main()
