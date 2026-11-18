# Python - historical Auctionet data

This folder documents how a historical dataset of **58,396 ended auctions** from
[auctionet.com](https://auctionet.com) was collected, enriched and validated.

The dataset covers auctions that ended between **12 October and 10 November 2026**
(30 days) across **87 auction houses**. It complements the daily pipeline in this
repository ([`azure-factory`](../azure-factory) → [`snowflake`](../snowflake) →
[`dbt`](../dbt)) with a longer history.

## How the data was built

The work was done step by step in a Jupyter notebook over several sessions, with
checkpoints and checks along the way. This folder contains a cleaned-up version
of the code that was actually used for the final dataset, split into three steps.

| Step | Script | What it does | Output |
|---|---|---|---|
| 1. Collection | `01_collect_ended_auctions.py` | Reads ended auctions from Auctionet search pages, per auction house, back to 1 July 2026. Saves a checkpoint after every page. | `auctionet_historical_combined.csv` (221,433 items), `auctionet_house_coverage.csv` |
| 2. Enrichment | `02_enrich_categories.py` | Visits item pages to add auction house name, main category and subcategory for the 30-day window. Reuses categories already in Snowflake. Runs in resumable batches. | `auctionet_enrichment_progress.csv` |
| 3. Validation & export | `03_build_final_dataset.py` | Combines all sources, fills missing house names, validates key fields and exports the final file. | `auctionet_historical_30days_final.csv` |

Shared scraping functions are in `src/auctionet_scraping.py`.

### 1. Collection

- Auctionet search pages embed their results as JSON (`data-react-props`), which is
  parsed directly.
- Results are sorted by most recently sold, so collection stops for a house as soon as
  a page contains items older than 1 July 2026.
- After every page the results are saved to a checkpoint file. If a run is interrupted,
  nothing is lost.
- Safety checks stop the run if a page is empty or if the date order is unexpected.
- The first house (Lawrences, `company_id=319`) was used as a pilot to test the approach
  before running all other houses.

### 2. Enrichment

Search pages do not include categories, so each item page has to be visited. To avoid
unnecessary requests:

- 9,012 items already had a category in the existing Snowflake data (dbt model
  `stg_auctionet_ended`) and were not fetched again.
- Every attempted item is logged, so no page is requested twice.
- Batches are spread across all end dates, so a partial run still covers the whole period.
- Requests are spaced 1–2 seconds apart, and the run stops on HTTP 403/429/5xx.

### 3. Validation & export

- Categories from Snowflake take priority over newly scraped ones.
- Items whose category came from Snowflake had no auction house name. Since the name is
  the same for every item of a `company_id`, it was copied from other items of the same house.
- The script checks for duplicates, missing values and invalid prices, estimates and bid counts.
- Output files are never overwritten, and the exported file is read back to verify it.

## Final dataset

| Check | Result |
|---|---|
| Auctions | 58,396 (all unique `item_id`) |
| Auction houses | 87 |
| Period | 2026-10-12 – 2026-11-10 |
| With main category | 58,221 (175 without) |
| With subcategory | 56,500 |
| Missing price, estimate, bid count, auction house | 0 |
| Currencies (of `estimate`) | SEK 48,760 · GBP 4,272 · DKK 2,730 · EUR 2,634 |

### Columns

| Column | Description |
|---|---|
| `item_id` | Auctionet item ID |
| `auction_id` | Auction ID |
| `estimate` | Estimate in the auction house's currency |
| `currency` | Currency of the estimate |
| `bid_count` | Number of bids |
| `hammer_price_sek` | Hammer price as shown on auctionet.com/sv |
| `auction_end_time` | End time as shown on the site (Swedish text) |
| `end_date` | Parsed end date |
| `reserve_met` | Whether the reserve price was met |
| `url` | Relative item URL |
| `source_page` | Search result page the item was found on |
| `company_id`, `auction_house` | Auction house |
| `main_category_id`, `main_category_name` | Main category |
| `subcategory_id`, `subcategory_name` | Subcategory |

## Known limitations

- **175 items have no category.** Their item pages did not contain category links.
- **Auctionet shows at most about 10,000 results per search** (209 pages). Two large houses
  hit this limit and their collection starts later than 1 July (8 and 17 July). This does
  not affect the final 30-day window.
- **Items without a parsable end date were skipped** during collection.
- The scrapers depend on Auctionet's current page structure and may break if it changes.

## Running the code

Run all commands from this `python` folder:

```bash
cd python
pip install -r requirements.txt

python 01_collect_ended_auctions.py        # collection + combine
python 02_enrich_categories.py 1000        # one enrichment batch (repeat until done)
python 03_build_final_dataset.py           # validate + export
```

Step 2 expects `data/auctionet_existing_categories.csv`, an export of item categories
that already existed in Snowflake, from the dbt model `stg_auctionet_ended` (columns `item_id`, `main_category_id`,
`main_category_name`, `subcategory_id`, `subcategory_name`).

All generated files go to `python/data/`, which is not committed to the repository.

> **Note:** You do not need to run the scraping again to use the dataset. The scripts
> document how it was built.

## Folder structure

```
python/
├── README.md
├── requirements.txt
├── .gitignore
├── 01_collect_ended_auctions.py
├── 02_enrich_categories.py
├── 03_build_final_dataset.py
└── src/
    └── auctionet_scraping.py
```

## Responsible scraping

The collection only reads public pages, uses a delay between every request and stops
automatically when the site returns rate-limit or server errors.
