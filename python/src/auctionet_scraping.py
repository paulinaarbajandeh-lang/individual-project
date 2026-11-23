"""
Shared helpers for collecting ended auctions from auctionet.com.

These functions are the ones that were used in the final collection and
enrichment runs (originally developed step by step in a Jupyter notebook).
"""

import html
import json
import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://auctionet.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 30

# All generated files are written to this folder (not committed to git).
DATA_DIR = Path("data")

# Collection goes back to this date for every auction house.
HISTORY_START = pd.Timestamp("2026-07-01")

# The final dataset covers this 30-day window (both dates inclusive).
PERIOD_START = "2026-10-12"
PERIOD_END = "2026-11-10"

# Swedish month abbreviations used in the "auction end time" text.
SWEDISH_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3,
    "apr": 4, "maj": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9,
    "okt": 10, "nov": 11, "dec": 12,
}


def scrape_ended_page(page_number, company_id):
    """Return one search result page of ended auctions for one auction house.

    The search page embeds its results as JSON in a React component
    (data-react-props), so no HTML table parsing is needed.
    Results are ordered by most recently sold first.
    """
    url = (
        f"{BASE_URL}/sv/search"
        f"?company_id={company_id}"
        f"&is=ended&order=sold_recent&page={page_number}"
    )

    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    react_div = soup.find("div", attrs={"data-react-class": "ErrorBoundary"})
    props = json.loads(html.unescape(react_div.get("data-react-props")))

    rows = []
    for item in props["items"]:
        # "amountLabel" contains the number of bids, e.g. "12 bud"
        bid_match = re.search(r"\d+", item.get("amountLabel", "") or "")
        bid_count = int(bid_match.group()) if bid_match else None

        # "amountValue" is the formatted hammer price, e.g. "1 200 SEK"
        price_digits = re.sub(r"[^\d]", "", item.get("amountValue", "") or "")
        hammer_price_sek = int(price_digits) if price_digits else None

        rows.append({
            "item_id": item.get("id"),
            "auction_id": item.get("auctionId"),
            "estimate": item.get("estimate"),
            "currency": item.get("currency"),
            "bid_count": bid_count,
            "hammer_price_sek": hammer_price_sek,
            "auction_end_time": item.get("auctionEndTime"),
            "reserve_met": item.get("hasMetReserve"),
            "url": item.get("url"),
            "source_page": page_number,
        })

    return pd.DataFrame(rows)


def parse_auction_date(text):
    """Turn Swedish date text such as '14 okt 2026 ...' into a date.

    Returns NaT when the text has no recognisable date.
    """
    match = re.search(r"(\d{1,2})\s+([a-zåäö]+)\s+(\d{4})", str(text).lower())
    if not match:
        return pd.NaT

    day, month, year = match.groups()
    month_number = SWEDISH_MONTHS.get(month)
    if month_number is None:
        return pd.NaT

    return pd.to_datetime(
        f"{year}-{month_number:02d}-{int(day):02d}", errors="coerce"
    )


def extract_item_enrichment(relative_url):
    """Read auction house and category information from one item page.

    The item page links back to filtered search pages. Those links contain
    the company_id (auction house) and the category IDs:
    the first category link is the main category, the second the subcategory.
    """
    response = requests.get(
        BASE_URL + relative_url, headers=HEADERS, timeout=TIMEOUT
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    result = {
        "company_id": None,
        "auction_house": None,
        "main_category_id": None,
        "main_category_name": None,
        "subcategory_id": None,
        "subcategory_name": None,
    }

    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        href = link["href"]

        company_match = re.search(r"company_id=(\d+)", href)
        if company_match and "is=ended" in href and result["company_id"] is None:
            result["company_id"] = int(company_match.group(1))
            result["auction_house"] = text

        category_match = re.search(r"/sv/search/(\d+)-", href)
        if category_match and "company_id=" in href and "is=ended" in href:
            category_id = int(category_match.group(1))
            if result["main_category_id"] is None:
                result["main_category_id"] = category_id
                result["main_category_name"] = text
            elif result["subcategory_id"] is None:
                result["subcategory_id"] = category_id
                result["subcategory_name"] = text

    return pd.Series(result)
