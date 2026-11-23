# Azure Data Factory: Automated Data Collection

This folder contains the Azure Data Factory (ADF) resources that collect active auction data and category data from the Auctionet API and store them as JSON files in Azure Blob Storage.

The files are generated and committed automatically by ADF through its Git integration. They describe the pipeline as it runs in Azure and should be changed in ADF Studio, not edited directly in GitHub.

## Position in the Pipeline

**Auctionet API → Azure Data Factory → Azure Blob Storage → Snowflake → dbt → Power BI**

ADF is responsible for the first step. New files in Blob Storage trigger Snowpipe, which loads them into Snowflake (see [`snowflake/`](../snowflake/)).

## Folder Structure

| Folder / file | Description |
|---|---|
| `pipeline/pl_ingest_auctionet.json` | The ingestion pipeline: collects all pages of active items and the category list. |
| `trigger/tr_twice_a_day.json` | Schedule trigger that runs the pipeline every 12 hours. |
| `linkedService/ls_auctionet.json` | Connection to the Auctionet REST API (`https://auctionet.com/api/v2/`), anonymous access. |
| `linkedService/sink_auctionet.json` | Connection to Azure Blob Storage. The credential is stored encrypted in ADF and is not included in the repository. |
| `dataset/ls_auctionet_dataset.json` | REST source dataset with a parameterised relative URL. |
| `dataset/sink_auctionet_dataset.json` | JSON sink dataset in the `raw` container with parameterised folder and file name. |
| `publish_config.json` | ADF Git setting: published resources are written to the `adf_publish` branch. |

## Pipeline Logic

`pl_ingest_auctionet` runs three activities in sequence:

1. **Get total pages**: a Web activity requests the first page of `items.json` and reads `pagination.total_pages` from the response.
2. **ForEach page**: loops sequentially over every page number and runs a Copy activity for each page. Each page is saved as a separate file:
   `raw/paginated/auctionet_data_<yyyyMMdd_HHmmss>_page_<n>.json` (timestamp in UTC)
3. **Copy Auctionet categories**: after all pages are collected, the category list is saved to `raw/categories/categories.json`. This file is overwritten on each run.

Pages are collected sequentially to keep the load on the Auctionet API low. A full run collects roughly 200 pages (about 10,000 active items) and takes around one hour.

Each run produces a new set of timestamped files. Snowflake therefore keeps every run as a separate snapshot, and dbt builds the current dataset from the most recent file for each page, keeping one row per item.

## Schedule

The trigger `tr_twice_a_day` runs the pipeline every 12 hours, starting at 18:00 in the `W. Europe Standard Time` zone (Swedish time). This gives two snapshots per day.

## Notes

- Activities have no automatic retry configured. A failed run is visible in ADF Monitor and can be re-run manually.
- The Copy activities use 4 Data Integration Units, the minimum allowed setting, to keep costs low.
- The storage account name is visible in the linked service. No keys or secrets are stored in this repository.
- The `adf_publish` branch is managed by ADF and should not be merged into `main`.
