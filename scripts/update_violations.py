#!/usr/bin/env python3
"""
Scrape Dedrone’s Drone-Violations database and emit data/violations.json
"""

from __future__ import annotations
import json, os, re, datetime as dt
import requests
from bs4 import BeautifulSoup

URL  = "https://www.dedrone.com/drone-violations-database"
OUT  = os.path.join("data", "violations.json")

# -----------------------------------------------------------------------------
_rx_year   = re.compile(r"^(19|20)\d{2}$")           # 1900-2099
_rx_num    = re.compile(r"\d[\d,]*")                 # 12,345
_rx_month  = re.compile(r"monthly-total-violations-(\d{4})")
_rx_wrap   = re.compile(r"cl-wrapper-([a-z]+)-(\d{4})")

def _int(text: str) -> int | None:
    """Return the first comma-less int in *text*, unless it is just a year."""
    m = _rx_num.search(text)
    if not m:
        return None
    val = int(m.group().replace(",", ""))
    return None if _rx_year.match(str(val)) else val

def fetch_html() -> BeautifulSoup:
    print("GET", URL)
    html = requests.get(URL, timeout=30).text
    return BeautifulSoup(html, "html.parser")

# -----------------------------------------------------------------------------
def yearly_totals(soup: BeautifulSoup) -> dict[str, int]:
    boxes = soup.select(".cl-wrapper-total .totals")
    years = ["2023", "2024", "2025"][: len(boxes)]
    return {y: int(b.text.strip()) for y, b in zip(years, boxes)}

def monthly_totals(soup: BeautifulSoup) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}

    # (A) hidden elements with explicit class
    for tag in soup.select("div[class*='monthly-total-violations-']"):
        yr = _rx_month.search(" ".join(tag["class"])).group(1)
        if num := _int(tag.text):
            out.setdefault(yr, []).append(num)

    # (B) fallback: wrapper lists cl-wrapper-monthly-YYYY
    for wrap in soup.select("div[class*='cl-wrapper-monthly-']"):
        m = _rx_wrap.search(" ".join(wrap["class"]))
        if not m:
            continue
        seg, yr = m.groups()          # seg == 'monthly'
        for item in wrap.select("[role='listitem'] .totals"):
            if num := _int(item.text):
                out.setdefault(yr, []).append(num)

    # keep the first 12 entries (Jan-Dec)
    return {y: vals[:12] for y, vals in out.items()}

def category_cards(soup: BeautifulSoup) -> tuple[dict[str,int], dict[str,dict[str,int]]]:
    totals, breakdown = {}, {}
    for card in soup.select("div:has(.x-dic-text-total)"):
        lbl_tag = card.select_one(".x-dic-label")
        val_tag = card.select_one(".x-dic-text-total")
        if not (lbl_tag and val_tag):
            continue

        label = re.sub(r"\s+", " ", lbl_tag.text.strip())
        totals[label] = _int(val_tag.text)

        sub: dict[str, int] = {}
        for line in card.select(".x-cl-item-dic-totals"):
            if (yrm := re.search(r"\[(\d{4})]", line.text)):
                if num := _int(line.text):
                    sub[yrm.group(1)] = num
        if sub:
            breakdown[label] = sub
    return totals, breakdown

def generic_segments(soup: BeautifulSoup) -> dict[str, dict[str, list[int]]]:
    segs: dict[str, dict[str, list[int]]] = {}

    for wrap in soup.select("div[class*='cl-wrapper-']"):
        if not (m := _rx_wrap.search(" ".join(wrap["class"]))):
            continue
        seg, yr = m.groups()

        for item in wrap.select("[role='listitem'] .totals, [role='listitem'] .x-dic-text-total"):
            if num := _int(item.text):
                segs.setdefault(seg, {}).setdefault(yr, []).append(num)

    return segs

# -----------------------------------------------------------------------------
def main() -> None:
    soup = fetch_html()

    data = {
        "yearly_totals"      : yearly_totals(soup),
        "monthly_totals"     : monthly_totals(soup),
        "category_totals"    : {},
        "category_breakdowns": {},
        "segments"           : generic_segments(soup),
        "scraped_at"         : dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    }

    cat_tot, cat_break = category_cards(soup)
    data["category_totals"]     = cat_tot
    data["category_breakdowns"] = cat_break

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {OUT} — "
          f"yearly:{len(data['yearly_totals'])} | "
          f"monthly arrays:{sum(len(v) for v in data['monthly_totals'].values())} | "
          f"segments:{list(data['segments'])}")

if __name__ == "__main__":
    main()
