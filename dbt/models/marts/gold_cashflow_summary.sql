with transactions as (
    select * from {{ ref('stg_transactions') }}
),

cashflow_summary as (
    select
        user_id,
        direction,
        currency,
        sum(amount) as total_volume,
        count(*) as transaction_count,
        round(avg(amount), 2) as avg_amount,
        min(amount) as min_amount,
        max(amount) as max_amount
    from transactions
    group by
        user_id,
        direction,
        currency
)

select * from cashflow_summary

