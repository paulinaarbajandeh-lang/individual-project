# dbt: Transformation and Prioritisation Model

This folder contains the dbt project that transforms raw auction data in Snowflake into
the tables used by the Power BI dashboard. It also contains the prioritisation model itself.

The project runs in dbt Cloud. A scheduled job (`auctionetdeploy`) runs `dbt build` after
each Azure Data Factory ingestion, so every model is rebuilt and tested automatically.

## Layers

| Layer | Prefix | Purpose | Materialisation |
|---|---|---|---|
| Staging | `stg_` | Unpack raw JSON, rename columns and set data types. No business logic. | Views |
| Intermediate | `int_` | Cleaning, currency conversion, aggregations and the prioritisation logic. | Views |
| Marts | `fct_`, `dim_` | Final tables for reporting. Power BI reads only from this layer. | Tables |

## Data flow

The project has three source branches that come together in the prioritisation model.

**Active auctions (Auctionet API, via Azure Data Factory and Snowpipe)**
- `stg_auctionet_items_current`: keeps the latest file per page and one row per item. This is the current snapshot of about 10,000 active items.
- `int_auctionet_items_cleaned`: converts estimates and starting bids to SEK, removes HTML tags and converts Unix timestamps.
- Marts: `fct_auctions`, `fct_bids`, `dim_items` and `dim_houses`. `dim_houses` adds the country from the seed `location_country_map`.

**Categories (Auctionet API)**
- `stg_auctionet_categories` flattens the two-level category tree.
- `dim_categories` contains main categories and subcategories with their parent IDs.

**Historical auctions (collected with Python, imported once)**
- `stg_auctionet_ended` reads the 58,396 ended auctions.
- `int_auctionet_ended_cleaned` calculates how far each hammer price was above or below the estimate (`hammer_vs_estimate_pct`).
- `fct_ended_auctions` has one row per ended auction.
- `int_historical_category_performance` and `int_historical_house_performance` aggregate the auctions per main category and per auction house.
- `fct_historical_category_performance` and `fct_historical_house_performance` expose these aggregates to Power BI.

**Prioritisation**
- `int_active_items_with_historical_performance` combines each active item with its bid count, main category, auction house and the historical performance of that category and house. All joins are left joins, so items without history are kept.
- `int_active_item_prioritisation` calculates the engagement score, confidence factors, Priority Score and rank.
- `fct_active_item_prioritisation` adds Stockholm timestamps, a bid-count baseline ranking and the Top 100 comparison groups.

## Prioritisation model

```
Priority Score = 0.50 × Engagement
               + 0.25 × Category % above estimate × Category confidence
               + 0.25 × House % above estimate × House confidence
```

- **Engagement** is the percentile rank of the item's current number of bids (`PERCENT_RANK`), from 0 to 1.
- **% above estimate** is the share of historical auctions in the item's main category or auction house that sold above estimate. It is 0 when no history is available.
- **Confidence** depends on the number of historical auctions: ≥ 100 → 1.0, ≥ 30 → 0.75, ≥ 10 → 0.50, otherwise 0.25.

The weights and confidence thresholds are analytical assumptions, not statistically optimised.

## Tests

Tests are defined in the `.yml` file in each layer folder and run as part of every `dbt build`:

- `unique` and `not_null` on primary keys, such as `item_id`, `category_id`, `company_id` and `bid_id`
- `relationships` from `fct_auctions` and `fct_bids` to the dimension tables
- `not_null` on all score and rank columns in the prioritisation models
- `accepted_values` on `top_100_group`

If a test fails, the models that depend on it are not built. This stops incorrect data from reaching Power BI.

## Folder structure

```
dbt/
├── dbt_project.yml
├── seeds/
│   └── location_country_map.csv
└── models/
    ├── source.yml
    ├── staging/        (_staging.yml + stg_ models)
    ├── intermediate/   (_intermediate.yml + int_ models)
    └── marts/          (_marts.yml + fct_ and dim_ models)
```

## Notes

- Currency conversion uses fixed exchange rates (EUR 11.10, GBP 12.80, DKK 1.49), defined in both `int_auctionet_items_cleaned` and `int_auctionet_ended_cleaned`.
- The three historical models up to `fct_ended_auctions` have no `config()` block. They are built as views in the default schema rather than in the `staging`, `intermediate` and `marts` schemas. This does not affect the results.
- The historical data is a one-off import and is not refreshed by the scheduled job. See [`../python/`](../python/) and [`../snowflake/04_historical_auction_ingestion.sql`](../snowflake/04_historical_auction_ingestion.sql).
