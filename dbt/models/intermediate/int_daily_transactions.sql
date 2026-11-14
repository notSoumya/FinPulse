with transactions as (
    select * from {{ ref('stg_transactions') }}
),

daily_grouped as (
    select
        user_id,
        transaction_date,
        currency,
        direction,
        count(*) as transaction_count,
        sum(amount) as total_amount
    from transactions
    group by
        user_id,
        transaction_date,
        currency,
        direction
)

select * from daily_grouped

