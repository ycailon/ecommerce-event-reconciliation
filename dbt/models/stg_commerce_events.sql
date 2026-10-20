-- Illustrative dbt model for a pre-existing, company-controlled BigQuery raw table.
select
    cast(event_id as string) as event_id
    , cast(event_type as string) as event_type
    , cast(order_id as string) as order_id
    , cast(amount_cents as int64) as amount_cents
    , cast(currency as string) as currency
    , timestamp(occurred_at) as occurred_at
from {{ source('commerce', 'commerce_events') }}
