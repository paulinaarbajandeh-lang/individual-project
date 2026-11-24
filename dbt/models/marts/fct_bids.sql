{{ config(
    materialized='table',
    schema='marts'
) }}

SELECT
    item_id,
    bid_id,
    bidder_id,
    bid_amount,
    your_bid,
    reserve_met,
    auto_bid,
    bid_timestamp_epoch,
    ingested_at
FROM {{ ref('int_auctionet_bids') }}