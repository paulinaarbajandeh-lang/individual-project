{{ config(
    materialized='table',
    schema='marts'
) }}

-- Historical performance per auction house, exposed for reporting in Power BI.
-- Built on top of the intermediate model, which is also used by the prioritisation model.

select
    company_id,
    auction_house,
    ended_items,
    avg_bid_count,
    median_bid_count,
    avg_hammer_vs_estimate_pct,
    median_hammer_vs_estimate_pct,
    pct_above_estimate
from {{ ref('int_historical_house_performance') }}