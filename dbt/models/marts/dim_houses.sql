{{ config(
    materialized='table',
    schema='marts'
) }}

SELECT
    company_id,
    house_name,
    location,
    country
FROM {{ ref('int_auction_houses') }}