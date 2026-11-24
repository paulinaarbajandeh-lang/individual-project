-- 01 Snowflake infrastructure
-- Database, schema, Azure integration, file format, stages and raw tables

-- 1. DATABASE AND SCHEMA
-- Create the database and RAW schema if they do not exist
-- RAW stores the original JSON data before dbt transformations

CREATE DATABASE IF NOT EXISTS DBT_AUCTIONET;

CREATE SCHEMA IF NOT EXISTS DBT_AUCTIONET.RAW;

USE DATABASE DBT_AUCTIONET;
USE SCHEMA RAW;


-- 2. AZURE STORAGE INTEGRATION
-- Establish a secure connection between Snowflake and Azure Blob Storage without embedding storage credentials
-- The Azure tenant ID and storage account are represented by placeholders for public GitHub documentation
-- Azure-side permissions must also be configured separately

CREATE STORAGE INTEGRATION IF NOT EXISTS AZURE_RAW_INTEGRATION
    TYPE = EXTERNAL_STAGE
    STORAGE_PROVIDER = 'AZURE'
    ENABLED = TRUE
    AZURE_TENANT_ID = '<AZURE_TENANT_ID>'
    STORAGE_ALLOWED_LOCATIONS = (
        'azure://<STORAGE_ACCOUNT>.blob.core.windows.net/raw/'
    );

-- 3. JSON FILE FORMAT
-- Define how Snowflake interprets JSON files collected from the Auctionet API

CREATE FILE FORMAT IF NOT EXISTS DBT_AUCTIONET.RAW.FORMAT_JSON_RAW
    TYPE = 'JSON'
    STRIP_OUTER_ARRAY = TRUE
    IGNORE_UTF8_ERRORS = TRUE;

-- 4. AZURE EXTERNAL STAGE
-- Stages provide Snowflake with access to JSON files stored in Azure Blob Storage
-- AZURE_PAGINATED_STAGE: References paginated item data collected by ADF
-- The category stage is created in 03_category_data_ingestion.sql

CREATE STAGE IF NOT EXISTS DBT_AUCTIONET.RAW.AZURE_PAGINATED_STAGE
    URL = 'azure://<STORAGE_ACCOUNT>.blob.core.windows.net/raw/paginated/'
    STORAGE_INTEGRATION = AZURE_RAW_INTEGRATION
    FILE_FORMAT = DBT_AUCTIONET.RAW.FORMAT_JSON_RAW;


-- 5. RAW DATA TABLES
-- Store API responses as semi-structured JSON (VARIANT).
-- JSON_DATA: Original JSON payload from Auctionet 
-- FILE_PATH: Identifies the source file in Azure Blob Storage
-- INGESTED_AT: Records when Snowflake ingested the data, using Swedish local time
-- Paginated active auction data
-- Historical snapshots are retained across ingestion runs

CREATE TABLE IF NOT EXISTS DBT_AUCTIONET.RAW.RAW_AUCTIONET_PAGINATED (
    JSON_DATA VARIANT,
    FILE_PATH STRING,
    INGESTED_AT TIMESTAMP_NTZ
        DEFAULT CONVERT_TIMEZONE(
            'Europe/Stockholm',
            CURRENT_TIMESTAMP()
        )::TIMESTAMP_NTZ
);



-- 6. KEY-PAIR AUTHENTICATION
-- dbt Cloud and Power BI connect to Snowflake with key-pair authentication, since password login requires multi-factor authentication for this account
-- The public key is registered on the Snowflake user.
-- The private keys are stored locally and in the dbt Cloud deployment credentials, and are never committed to GitHub.

ALTER USER <SNOWFLAKE_USER> SET RSA_PUBLIC_KEY = '<PUBLIC_KEY>';

-- Verify that the key is registered (RSA_PUBLIC_KEY_FP should have a value)
DESC USER <SNOWFLAKE_USER>;
