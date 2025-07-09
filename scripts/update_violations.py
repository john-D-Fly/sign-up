#!/usr/bin/env python3
"""
Scrape Dedrone’s Drone-Violations page and emit structured JSON for Decentrafly.

Outputs ➜  data/violations.json
"""

from __future__ import annotations
import json, os, re, datetime as dt
import requests
from bs4 import BeautifulSoup

URL  = "https://www.dedrone.com/drone-violations-database"
OUT  = os.path.join("data", "violations.json")

def _clean(num: str) -> int:
    """Turn '412,658' ⇒ 412658"""
    return int(re.sub(r"[^\d]", "", num))

def fetch_html() -> str:
    print("Downloading", URL)
    res = requests.get(URL, timeout=30)
    res.raise_for_status()
    return res.text

def parse_yearly_totals(soup: BeautifulSoup) -> dict[str, int]:
    """
    <div class="cl-wrapper-total w-dyn-list">
       <div role="listitem" …>
         <div class="totals">1067112</div>
    """
    totals = [ _clean(div.text) for div in soup.select(".cl-wrapper-total .totals") ]
    # Map to 2023, 2024, 2025 in the order they appear (Dedrone page is oldest-→newest)
    years  = [ "2023", "2024", "2025" ][: len(totals)]
    return dict(zip(years, totals))

def parse_monthly_totals(soup: BeautifulSoup) -> dict[str, list[int]]:
    """
    <div class="monthly-total-violations-2023">60266</div>
    Twelve such divs per year (hidden but in DOM).
    """
    monthly: dict[str, list[int]] = {}
    for div in soup.select("div[class*=monthly-total-violations-]"):
        raw = div.get_text(strip=True)
        if not raw:
            continue
        num  = _clean(raw)
        # Extract year from the class name
        for cls in div["class"]:
            m = re.search(r"monthly-total-violations-(\d{4})", cls)
            if m:
                year = m.group(1)
                monthly.setdefault(year, []).append(num)
                break
    return monthly

def parse_category_totals(soup: BeautifulSoup) -> dict[str, int]:
    """
    <div class="x-dic-wrapper">
         <div class="x-dic-label">FAA 400 ft.</div>
         …
         <div class="x-dic-text-total">412,658</div>
    """
    data: dict[str, int] = {}
    for wrap in soup.select(".x-dic-wrapper"):
        label_tag = wrap.select_one(".x-dic-label")
        total_tag = wrap.select_one(".x-dic-text-total")
        if label_tag and total_tag:
            label = re.sub(r"\s+", " ", label_tag.get_text(strip=True))
            data[label] = _clean(total_tag.get_text())
    return data

def main() -> None:
    html  = fetch_html()
    soup  = BeautifulSoup(html, "html.parser")

    payload = {
        "yearly_totals"   : parse_yearly_totals(soup),
        "monthly_totals"  : parse_monthly_totals(soup),
        "category_totals" : parse_category_totals(soup),
        "scraped_at"      : dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    }

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT} with {len(payload['yearly_totals'])} yearly totals, "
          f"{sum(len(v) for v in payload['monthly_totals'].values())} monthly points, "
          f"{len(payload['category_totals'])} category cards.")

if __name__ == "__main__":
    main()
