-- Illustrative BigQuery adaptation, not deployed or benchmarked.
-- Use a project-owned dataset and least-privilege service account in production.
with latest as (
    select
        order_id
        , event_type
        , amount_cents
        , currency
        , row_number() over (
            partition by order_id, event_type
            order by occurred_at desc, event_id desc
        ) as rn
    from
        `YOUR_PROJECT.analytics.commerce_events`
)
, events as (
    select
        *
    from
        latest
    where
        rn = 1
)
, paid as (
    select
        order_id
        , amount_cents
        , currency
    from
        events
    where
        event_type = 'order_paid'
)
, checkout as (
    select
        order_id
        , amount_cents
        , currency
    from
        events
    where
        event_type = 'checkout_completed'
)
select
    coalesce(p.order_id, c.order_id) as order_id
    , case
        when p.order_id is null then 'checkout_without_order'
        when c.order_id is null then 'order_without_checkout'
        when p.amount_cents != c.amount_cents or p.currency != c.currency then 'amount_or_currency_mismatch'
        else 'matched'
    end as reconciliation_status
from
    paid p
full outer join
    checkout c
    on p.order_id = c.order_id
;
