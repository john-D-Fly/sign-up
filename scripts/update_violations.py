#!/usr/bin/env python3
"""
Scrape Dedrone’s Drone-Violations page for Decentrafly.

Outputs -> data/violations.json   (over-writes on every run)
"""

from __future__ import annotations
import json, os, re, datetime as dt
import requests
from bs4 import BeautifulSoup

URL = "https://www.dedrone.com/drone-violations-database"
OUT = os.path.join("data", "violations.json")

def _ints(text: str) -> list[int]:
    """Return all integer-like substrings in `text` → list[int]."""
    return [int(t.replace(",", "")) for t in re.findall(r"\d[\d,]*", text)]

def fetch_html() -> str:
    print("GET", URL)
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    return r.text

# ------------------------------------------------------------
# PARSERS
# ------------------------------------------------------------
def parse_yearly_totals(soup: BeautifulSoup) -> dict[str, int]:
    boxes = soup.select(".cl-wrapper-total .totals")
    years = ["2023", "2024", "2025"][: len(boxes)]
    return {y: int(b.get_text(strip=True)) for y, b in zip(years, boxes)}

def parse_monthly_totals(soup: BeautifulSoup) -> dict[str, list[int]]:
    data: dict[str, list[int]] = {}
    for div in soup.select("div[class*='monthly-total-violations-']"):
        nums = _ints(div.get_text())
        if not nums:
            continue
        year = re.search(r"monthly-total-violations-(\d{4})", " ".join(div["class"])).group(1)
        data.setdefault(year, []).extend(nums)
    # keep order-of-months stable (Dedrone markup is already Jan→Dec)
    return {y: vals[:12] for y, vals in data.items()}

def parse_category_totals(soup: BeautifulSoup) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """
    Big cards look like
      <div class="x-dic-label">FAA 400ft.</div>
      <div class="x-dic-text-total" wfu-format="comma">412,658</div>
      <div class="x-cl-item-dic-totals">808,648 [2024]</div>
      <div class="x-cl-item-dic-totals">678,095 [2023]</div>
    """
    totals: dict[str, int] = {}
    breakdowns: dict[str, dict[str, int]] = {}

    for card in soup.select("div:has(.x-dic-text-total)"):
        label_tag = card.select_one(".x-dic-label")
        total_tag = card.select_one(".x-dic-text-total")
        if not (label_tag and total_tag):
            continue

        label = re.sub(r"\s+", " ", label_tag.get_text(strip=True))
        totals[label] = _ints(total_tag.get_text())[0]

        # yearly breakdown lines
        sub: dict[str, int] = {}
        for subline in card.select(".x-cl-item-dic-totals"):
            nums = _ints(subline.get_text())
            year_match = re.search(r"\[(\d{4})]", subline.get_text())
            if nums and year_match:
                sub[year_match.group(1)] = nums[0]
        if sub:
            breakdowns[label] = sub

    return totals, breakdowns

# ------------------------------------------------------------
def main() -> None:
    html  = fetch_html()
    soup  = BeautifulSoup(html, "html.parser")

    yearly  = parse_yearly_totals(soup)
    monthly = parse_monthly_totals(soup)
    cats, cat_break = parse_category_totals(soup)

    payload = {
        "yearly_totals"      : yearly,
        "monthly_totals"     : monthly,
        "category_totals"    : cats,
        "category_breakdowns": cat_break,
        "scraped_at"         : dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    }

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"→ {OUT}   yearly:{len(yearly)}  monthly:{sum(len(v) for v in monthly.values())} "
          f"categories:{len(cats)}")

if __name__ == "__main__":
    main()
