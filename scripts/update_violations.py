#!/usr/bin/env python3
"""
Scrape Dedrone’s Drone-Violations database for Decentrafly.

Outputs → data/violations.json
"""

from __future__ import annotations
import json, os, re, datetime as dt
import requests
from bs4 import BeautifulSoup

URL  = "https://www.dedrone.com/drone-violations-database"
OUT  = os.path.join("data", "violations.json")

# ---------------- helpers -----------------------------------------------------
_rx_num   = re.compile(r"\d[\d,]*")
_rx_wrap  = re.compile(r"cl-wrapper-([a-z]+)-(\d{4})")   # segment + year
_rx_month = re.compile(r"monthly-total-violations-(\d{4})")

def _to_int(txt: str) -> int:
    return int(txt.replace(",", ""))

def fetch_html() -> str:
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    return r.text

# ---------------- specific sections ------------------------------------------
def parse_yearly_totals(soup: BeautifulSoup) -> dict[str, int]:
    boxes = soup.select(".cl-wrapper-total .totals")
    years = ["2023", "2024", "2025"][: len(boxes)]
    return {y: _to_int(b.get_text(strip=True)) for y, b in zip(years, boxes)}

def parse_monthly_totals(soup: BeautifulSoup) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for div in soup.select("div[class*='monthly-total-violations-']"):
        nums = _rx_num.findall(div.get_text())
        if not nums:
            continue
        year = _rx_month.search(" ".join(div["class"])).group(1)
        out.setdefault(year, []).extend(_to_int(n) for n in nums)
    return {y: vals[:12] for y, vals in out.items()}

def parse_category_cards(soup: BeautifulSoup) -> tuple[dict[str,int], dict[str,dict[str,int]]]:
    totals, breakdowns = {}, {}
    for card in soup.select("div:has(.x-dic-text-total)"):
        lbl = card.select_one(".x-dic-label")
        val = card.select_one(".x-dic-text-total")
        if not (lbl and val): continue
        label = re.sub(r"\s+", " ", lbl.get_text(strip=True))
        totals[label] = _to_int(val.get_text())
        subs = {}
        for sub in card.select(".x-cl-item-dic-totals"):
            yr = re.search(r"\[(\d{4})]", sub.get_text())
            if yr:
                subs[yr.group(1)] = _to_int(_rx_num.search(sub.get_text()).group())
        if subs: breakdowns[label] = subs
    return totals, breakdowns

# ---------------- NEW generic segment parser ---------------------------------
def parse_segments(soup: BeautifulSoup) -> dict[str, dict[str, list[int]]]:
    """
    Captures any wrapper like:  <div class="cl-wrapper-INDUSTRY-2024 w-dyn-list">
    -> segments['industry']['2024'] = [numbers…]
    Works for 'industry', 'daily', 'hourly', and future segments they add.
    """
    segs: dict[str, dict[str, list[int]]] = {}

    for wrap in soup.select("div[class*='cl-wrapper-']"):
        m = _rx_wrap.search(" ".join(wrap["class"]))
        if not m:
            continue
        seg, year = m.groups()
        nums = [_to_int(x.get_text(strip=True))
                for x in wrap.select(".totals, .x-dic-text-total, .monthly-total")]  # fallback selectors
        if not nums:
            # Sometimes the numbers are direct text in listitems
            nums = [_to_int(t) for t in _rx_num.findall(wrap.get_text())]

        if nums:
            segs.setdefault(seg, {}).setdefault(year, []).extend(nums)

    return segs

# ---------------- orchestrator ------------------------------------------------
def main() -> None:
    soup = BeautifulSoup(fetch_html(), "html.parser")

    yearly   = parse_yearly_totals(soup)
    monthly  = parse_monthly_totals(soup)
    cats, cat_break = parse_category_cards(soup)
    segments = parse_segments(soup)          # NEW ‼️

    payload = {
        "yearly_totals"      : yearly,
        "monthly_totals"     : monthly,
        "category_totals"    : cats,
        "category_breakdowns": cat_break,
        "segments"           : segments,     # ← all other wrappers
        "scraped_at"         : dt.datetime.utcnow().isoformat(timespec="seconds")+"Z"
    }

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {OUT}  | segments captured: {list(segments.keys())}")

if __name__ == "__main__":
    main()
