# Power BI: Marketplace Prioritisation Dashboard

This folder contains the Power BI report for the Auctionet Marketplace Prioritisation project.
It supports a Marketplace Manager in selecting active items for extra visibility on the next day.

## Pages

| Page | What it shows |
|---|---|
| **Marketplace Prioritisation** | A Top 10 shortlist of items ending the next day, the relationship between current bids and Priority Score, two cards comparing the model's Top 100 with a Top 100 based on bid count only, and the historical performance of the categories and auction houses in each group. Category and Auction House slicers filter the page. |
| **Worked Example** | Titled *How the Priority Score Works*. A worked example of how an item's score is built from engagement, historical category performance and historical auction house performance, together with the formula. |
| **Marketplace Performance** | Titled *Historical Marketplace Performance*. The share of ended auctions sold above estimate per category and auction house, with the number of auctions behind each value (12 October – 10 November 2026). |

## Data model

The report connects to Snowflake with **DirectQuery** and reads only from the dbt mart layer
(`DBT_PAULINAARBAJANDEHLANG_MARTS`).

| Table | Source | Used for |
|---|---|---|
| `FCT_ACTIVE_ITEM_PRIORITISATION` | dbt mart | Top 10 table, scatter chart, Top 100 comparison and worked example |
| `FCT_HISTORICAL_CATEGORY_PERFORMANCE` | dbt mart | Historical category chart |
| `FCT_HISTORICAL_HOUSE_PERFORMANCE` | dbt mart | Historical auction house chart |
| `DIM_CATEGORIES` | dbt mart | English category names for the historical category chart and slicer |

There is one relationship: `FCT_HISTORICAL_CATEGORY_PERFORMANCE[MAIN_CATEGORY_ID]` → `DIM_CATEGORIES[CATEGORY_ID]`.
The historical data was collected from Auctionet's Swedish website, so category names are matched by ID to show the English names used elsewhere.

## Measures

| Measure | Purpose |
|---|---|
| `Engagement Contribution` | Engagement score × 0.50 |
| `Category Contribution` | Category % above estimate × confidence × 0.25 |
| `House Contribution` | Auction house % above estimate × confidence × 0.25 |
| `Hours to Close` | Hours remaining until the auction ends, calculated from the current time |
| `Shared Top 100` | Number of items in both the model's Top 100 and the bid-count Top 100 |
| `Ranking-Specific Top 100` | Number of items in only one of the two Top 100 lists |

The Top 100 measures always use the full snapshot and are not affected by the slicers.

## Opening the report

The report is saved in Power BI Project format (`.pbip`), which stores the report and the
semantic model as text files that can be version-controlled with git.

1. Open `auctionet_dashboard.pbip` in Power BI Desktop.
2. Refreshing the data requires access to the Snowflake account.

An exported PDF of the dashboard is included for review without database access.
