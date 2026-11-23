-- 04 Historical auction ingestion
-- Import, validation and replacement of the historical auction dataset
-- Source: auctionet_historical_30days_final.csv
-- Period: 12 October – 10 November 2026
-- The enriched CSV was imported into a separate validation table before replacing the existing historical raw dataset


-- 1. Import and validate historical auction data
-- The enriched CSV was exported from the Python notebook and uploaded using Snowflake's Table and From File interface
--
-- Source file: auctionet_historical_30days_final.csv
-- Destination: DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED_VALIDATION_20261113
-- Imported records: 58,396

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT item_id) AS unique_items,
    COUNT(*) - COUNT(DISTINCT item_id) AS duplicate_rows,
    COUNT_IF(main_category_id IS NULL) AS missing_categories,
    COUNT_IF(company_id IS NULL) AS missing_company_ids,
    COUNT_IF(auction_house IS NULL) AS missing_house_names,
    COUNT_IF(estimate IS NULL) AS missing_estimates,
    COUNT_IF(hammer_price_sek IS NULL) AS missing_hammer_prices
FROM DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED_VALIDATION_20261113;


-- 2. Check the imported date range

SELECT
    MIN(end_date) AS earliest_end_date,
    MAX(end_date) AS latest_end_date,
    COUNT(DISTINCT end_date) AS distinct_dates
FROM DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED_VALIDATION_20261113;


-- 3. Check the existing historical dataset

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT item_id) AS unique_items
FROM DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED;


-- 4. Back up the existing historical dataset

CREATE TABLE DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED_BACKUP_20261113
CLONE DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED;


-- 5. Verify the backup

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT item_id) AS unique_items
FROM DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED_BACKUP_20261113;


-- 6. Add columns required by the existing dbt models
-- These columns were added for schema compatibility
-- Their values remain NULL in the new dataset

ALTER TABLE DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED_VALIDATION_20261113
    ADD COLUMN IF NOT EXISTS HAS_BID_COUNT BOOLEAN;

ALTER TABLE DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED_VALIDATION_20261113
    ADD COLUMN IF NOT EXISTS SALE_FORMAT VARCHAR;


-- 7. Replace the existing historical data with the validated dataset
-- SWAP WITH exchanges the two tables
-- After the swap, the main table contains the new 58,396 records while the validation table contains the previous 9,268 records

ALTER TABLE DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED
SWAP WITH DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED_VALIDATION_20261113;


-- 8. Verify the replacement

SELECT
    'CURRENT' AS dataset,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT item_id) AS unique_items
FROM DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED

UNION ALL

SELECT
    'PREVIOUS' AS dataset,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT item_id) AS unique_items
FROM DBT_AUCTIONET.RAW.RAW_AUCTIONET_ENDED_ENRICHED_VALIDATION_20261113;


-- 9. Validate the historical fact model after the dbt build

SELECT
    COUNT(*) AS total_ended_auctions,
    COUNT(DISTINCT item_id) AS unique_items,
    COUNT_IF(main_category_id IS NULL) AS missing_categories,
    COUNT_IF(company_id IS NULL) AS missing_company_ids
FROM DBT_AUCTIONET.DBT_PAULINAARBAJANDEHLANG.FCT_ENDED_AUCTIONS;

-- Result: 58,396 historical auctions in FCT_ENDED_AUCTIONS
