"""
Step 2 – Enrichment

Adds auction house name and category (main category + subcategory)
to every item in the final 30-day window.

The search pages used in step 1 do not include categories, so each
item page has to be visited. To keep the number of requests down:
- Items that already had a category in the existing Snowflake data
  (exported to auctionet_existing_categories.csv) are not fetched again.
- Every item that has been attempted is stored in a progress file and
  is never requested twice.

The script runs in batches and can be stopped and restarted at any time.
In the original work it was run in many batches (100–10,000 items each)
over several sessions.
"""

import random
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.append(str(Path(__file__).parent / "src"))
from auctionet_scraping import (  # noqa: E402
    DATA_DIR,
    PERIOD_END,
    PERIOD_START,
    extract_item_enrichment,
)

COMBINED_FILE = DATA_DIR / "auctionet_historical_combined.csv"
EXISTING_CATEGORIES_FILE = DATA_DIR / "auctionet_existing_categories.csv"
PROGRESS_FILE = DATA_DIR / "auctionet_enrichment_progress.csv"

PROGRESS_COLUMNS = [
    "company_id",
    "auction_house",
    "main_category_id",
    "main_category_name",
    "subcategory_id",
    "subcategory_name",
    "item_id",
]


def load_period_items():
    """Items that ended within the 30-day window."""
    combined = pd.read_csv(COMBINED_FILE, low_memory=False)
    dates = pd.to_datetime(combined["end_date"], format="mixed", errors="coerce")
    period = combined[dates.between(PERIOD_START, PERIOD_END)].copy()

    print("Items in 30-day window:", len(period))
    print("Auction houses:", period["company_id"].nunique())
    return period


def items_to_enrich(period):
    """Remove items that already have a category or were already attempted."""
    existing = pd.read_csv(EXISTING_CATEGORIES_FILE)
    existing.columns = existing.columns.str.lower()
    has_category = set(
        existing.loc[existing["main_category_id"].notna(), "item_id"].astype(int)
    )

    if PROGRESS_FILE.exists():
        progress = pd.read_csv(PROGRESS_FILE)
        attempted = set(progress["item_id"].dropna().astype(int))
    else:
        attempted = set()

    remaining = period[~period["item_id"].isin(has_category | attempted)].copy()

    # Spread each batch across all end dates (round-robin by day),
    # so a partial run still covers the whole period evenly.
    remaining["day"] = pd.to_datetime(remaining["end_date"], errors="coerce").dt.date
    remaining = remaining.sort_values(["day", "item_id"])
    remaining["round"] = remaining.groupby("day", dropna=False).cumcount()
    return remaining.sort_values(["round", "day", "item_id"])


def enrich(batch_size=1000):
    period = load_period_items()
    remaining = items_to_enrich(period)
    batch = remaining.head(batch_size)

    print("Remaining items:", len(remaining))
    print("Starting batch:", len(batch))

    buffer = []
    with_category = without_category = errors = 0

    def save_progress():
        if buffer:
            pd.DataFrame(buffer).reindex(columns=PROGRESS_COLUMNS).to_csv(
                PROGRESS_FILE,
                mode="a",
                header=not PROGRESS_FILE.exists(),
                index=False,
            )
            buffer.clear()

    try:
        for _, row in batch.iterrows():
            try:
                result = extract_item_enrichment(row["url"]).to_dict()
                result["item_id"] = int(row["item_id"])
                buffer.append(result)

                if pd.notna(result["main_category_id"]):
                    with_category += 1
                else:
                    without_category += 1

            except requests.exceptions.HTTPError as e:
                errors += 1
                status = e.response.status_code if e.response is not None else None
                print("HTTP error:", row["item_id"], status)
                # Stop politely if the site signals too many requests or problems.
                if status in (403, 429) or (status is not None and status >= 500):
                    print("Stopping to avoid putting load on the server.")
                    break

            except requests.exceptions.RequestException as e:
                errors += 1
                print("Network error:", row["item_id"], e)
                break

            except Exception as e:  # unexpected page structure etc.
                errors += 1
                print("Error:", row["item_id"], e)
                if errors >= 3:
                    print("Too many errors. Stopping.")
                    break

            if len(buffer) >= 10:
                save_progress()

            time.sleep(random.uniform(1.0, 2.0))

    except KeyboardInterrupt:
        print("Stopped by user.")

    finally:
        save_progress()

    print("\nBatch finished")
    print("With category:", with_category)
    print("Without category:", without_category)
    print("Errors:", errors)


if __name__ == "__main__":
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    enrich(batch_size)
