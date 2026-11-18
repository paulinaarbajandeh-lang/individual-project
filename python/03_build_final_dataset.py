"""
Step 3 – Validation & Export

Builds the final 30-day dataset (12 Oct – 10 Nov 2026) by combining:
1. Collected auctions from step 1
2. Categories that already existed in Snowflake
3. Auction house and category information scraped in step 2

Then it fills missing auction house names, validates key fields and
exports the result. Existing output files are never overwritten.

Result of the original run:
- 58,396 auctions from 87 auction houses, no duplicate item IDs
- 58,221 items with a main category (175 without)
- No missing auction house, price, estimate or bid count
"""

import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

sys.path.append(str(Path(__file__).parent / "src"))
from auctionet_scraping import DATA_DIR, PERIOD_END, PERIOD_START  # noqa: E402

COMBINED_FILE = DATA_DIR / "auctionet_historical_combined.csv"
EXISTING_CATEGORIES_FILE = DATA_DIR / "auctionet_existing_categories.csv"
PROGRESS_FILE = DATA_DIR / "auctionet_enrichment_progress.csv"
FINAL_CSV = DATA_DIR / "auctionet_historical_30days_final.csv"
FINAL_ZIP = DATA_DIR / "auctionet_historical_30days_final.zip"

CATEGORY_COLS = [
    "item_id",
    "main_category_id",
    "main_category_name",
    "subcategory_id",
    "subcategory_name",
]
ENRICHMENT_FIELDS = [
    "company_id",
    "auction_house",
    "main_category_id",
    "main_category_name",
    "subcategory_id",
    "subcategory_name",
]


def load_inputs():
    combined = pd.read_csv(COMBINED_FILE, low_memory=False)
    dates = pd.to_datetime(combined["end_date"], format="mixed", errors="coerce")
    period = combined[dates.between(PERIOD_START, PERIOD_END)].copy()

    existing = pd.read_csv(EXISTING_CATEGORIES_FILE)
    existing.columns = existing.columns.str.lower()

    progress = pd.read_csv(PROGRESS_FILE, low_memory=False)
    progress.columns = progress.columns.str.lower()

    return period, existing, progress


def add_categories(period, existing, progress):
    """Attach categories. Existing (already validated) categories win."""
    categories = pd.concat(
        [existing[CATEGORY_COLS], progress[CATEGORY_COLS]], ignore_index=True
    )
    categories = categories.dropna(subset=["main_category_id"])
    categories = categories.drop_duplicates(subset=["item_id"], keep="first")

    return period.merge(categories, on="item_id", how="left")


def add_enrichment(base, progress):
    """Fill remaining gaps with everything scraped in step 2.

    Only missing values are filled; values already present are kept.
    """
    updates = progress[["item_id"] + ENRICHMENT_FIELDS].copy()
    # Prefer rows where a category was found, then keep one row per item.
    updates = updates.sort_values("main_category_id", na_position="last")
    updates = updates.drop_duplicates(subset=["item_id"], keep="first")
    updates = updates.rename(columns={f: f"{f}_saved" for f in ENRICHMENT_FIELDS})

    result = base.merge(updates, on="item_id", how="left", validate="one_to_one")

    for field in ENRICHMENT_FIELDS:
        saved = f"{field}_saved"
        if field in result.columns:
            result[field] = result[field].combine_first(result[saved])
        else:
            result[field] = result[saved]
        result = result.drop(columns=saved)

    return result


def fill_auction_house_names(df):
    """Items whose category came from Snowflake have no house name yet.

    The name is the same for every item of a company_id, so it is copied
    from other items of the same auction house.
    """
    known = df.dropna(subset=["company_id", "auction_house"])

    conflicts = known.groupby("company_id")["auction_house"].nunique()
    if (conflicts > 1).any():
        raise ValueError("Some company IDs have more than one house name.")

    lookup = known.drop_duplicates(subset=["company_id"]).set_index("company_id")["auction_house"]
    df["auction_house"] = df["auction_house"].fillna(df["company_id"].map(lookup))
    return df


def validate(df):
    print("Total rows:", len(df))
    print("Unique item IDs:", df["item_id"].nunique())
    print("Auction houses:", df["company_id"].nunique())
    print("Date range:", df["end_date"].min(), "–", df["end_date"].max())

    print("\nMissing values:")
    for col in [
        "item_id", "auction_id", "estimate", "currency", "bid_count",
        "hammer_price_sek", "company_id", "auction_house",
        "main_category_id", "subcategory_id",
    ]:
        print(f"  {col}: {df[col].isna().sum()}")

    estimate = pd.to_numeric(df["estimate"], errors="coerce")
    hammer = pd.to_numeric(df["hammer_price_sek"], errors="coerce")
    bids = pd.to_numeric(df["bid_count"], errors="coerce")

    print("\nValue checks:")
    print("  Invalid or non-positive estimates:", (estimate.isna() | (estimate <= 0)).sum())
    print("  Invalid or negative hammer prices:", (hammer.isna() | (hammer < 0)).sum())
    print("  Invalid or negative bid counts:", (bids.isna() | (bids < 0)).sum())

    print("\nCurrencies:")
    print(df["currency"].value_counts(dropna=False).to_string())

    # Hard requirements for the export
    assert df["item_id"].is_unique, "Duplicate item IDs"
    assert df["company_id"].notna().all(), "Missing company_id"
    assert df["auction_house"].notna().all(), "Missing auction house name"


def export(df):
    if FINAL_CSV.exists():
        print("\nFinal CSV already exists. Nothing was overwritten.")
    else:
        df.to_csv(FINAL_CSV, index=False, encoding="utf-8")
        print("\nSaved:", FINAL_CSV)

    # Read the file back to make sure the export is complete.
    saved = pd.read_csv(FINAL_CSV, low_memory=False)
    print("Rows in saved file:", len(saved))
    print("Unique items in saved file:", saved["item_id"].nunique())

    if not FINAL_ZIP.exists():
        with ZipFile(FINAL_ZIP, "w", compression=ZIP_DEFLATED) as z:
            z.write(FINAL_CSV, arcname=FINAL_CSV.name)
    with ZipFile(FINAL_ZIP) as z:
        print("ZIP integrity:", "OK" if z.testzip() is None else "FAILED")


if __name__ == "__main__":
    period, existing, progress = load_inputs()
    final = add_categories(period, existing, progress)
    final = add_enrichment(final, progress)
    final = fill_auction_house_names(final)
    validate(final)
    export(final)
