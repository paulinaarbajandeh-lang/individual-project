# Individual Project: Data-Driven Marketplace Prioritisation at Auctionet

## Project Overview

This project explores how Auctionet can combine current bidder engagement with historical auction outcomes to identify which active items should be prioritised for marketplace visibility.

**Research question:**
*How can Auctionet combine bidder engagement and historical auction outcomes to identify which active items should be prioritised for marketplace visibility?*

The main output is a rule-based prioritisation model and a set of Power BI dashboards designed to support a Marketplace Manager in selecting items for next-day promotional placement.

## Data Pipeline

The project uses the following data workflow:

**Auctionet API → Azure Data Factory → Azure Blob Storage → Snowflake → dbt → Power BI**

- **Azure Data Factory:** Collects active auction data through the Auctionet API.
- **Azure Blob Storage:** Stores the collected JSON files.
- **Snowflake:** Stores raw and transformed auction data.
- **dbt:** Cleans, transforms and combines current auction data with historical performance metrics.
- **Power BI:** Visualises the prioritisation results and supporting analysis.

Historical auction outcomes were collected separately with Python. The final historical dataset contains 58,396 ended auctions from 87 auction houses (12 October – 10 November 2026). It was imported into Snowflake once and is not part of the automated pipeline. See [`python/`](python/) for the collection and enrichment process.

## Prioritisation Model

Each active item receives a prioritisation score based on three components:

| Component | Weight | How it is measured |
|---|---:|---|
| Current bidder engagement | 50% | Percentile rank of the item's current number of bids |
| Historical category performance | 25% | Share of ended auctions in the item's main category that sold above estimate |
| Historical auction house performance | 25% | Share of ended auctions from the item's auction house that sold above estimate |

Historical performance is adjusted using confidence factors based on the number of observations available.

The model ranks items by their overall score. It is a transparent, rule-based prototype rather than a statistically validated predictive model.

## Project Outputs

**1. Prioritisation model (dbt)**

The main SQL model is located at:

[`dbt/models/intermediate/int_active_item_prioritisation.sql`](dbt/models/intermediate/int_active_item_prioritisation.sql)

Supporting models calculate historical category and auction house performance and prepare the final prioritisation dataset. Power BI reads only from the mart layer. See [`dbt/`](dbt/) for an overview of all models.

**2. Power BI dashboards**

The Power BI report contains three main pages:

- **Marketplace Prioritisation:** A Top 10 shortlist for next-day placement, ranking comparisons and historical performance metrics.
- **Worked Example:** An explanation of an individual item's score, including a breakdown of its contributing factors.
- **Marketplace Performance:** Historical category and auction house performance.

The report uses DirectQuery to Snowflake, so it cannot be refreshed without database access. The Power BI project files are in [`powerbi/`](powerbi/), together with an exported PDF of the dashboards.

**3. Technical implementation**

| Folder | Contents |
|---|---|
| [`azure-factory/`](azure-factory/) | Azure Data Factory pipeline and trigger for active auction data |
| [`snowflake/`](snowflake/) | SQL scripts for infrastructure, data ingestion, data quality and model evaluation |
| [`dbt/`](dbt/) | dbt models for staging, historical performance and prioritisation |
| [`python/`](python/) | Collection, enrichment and validation of the historical auction dataset |
| [`powerbi/`](powerbi/) | Power BI project files and dashboard export |

## How to Review the Project

1. Review the prioritisation model in `dbt/models/intermediate/`.
2. Explore the Power BI dashboards or the exported PDF in `powerbi/`.
3. Refer to the Project Report for the methodology, design decisions, findings and limitations.

## Limitations

The prioritisation model uses manually selected weights and sample-size-based confidence factors. Historical data covers 30 days and is not updated automatically. Each snapshot of active items contains around 10,000 items, mainly auctions ending within the next few days, rather than Auctionet's full active catalogue. Currency conversion uses fixed exchange rates, and the model has not yet been validated against future auction outcomes or tested through a real placement experiment.

The project is intended as a decision-support prototype, not a proven method for increasing auction revenue.
