with transactions as (
    select * from {{ ref('stg_transactions') }}
),

merchant_stats as (
    select
        user_id,
        merchant_name,
        currency,
        sum(case when direction = 'DEBIT' then amount else 0 end) as total_spent,
        count(*) as transaction_count,
        round(avg(case when direction = 'DEBIT' then amount else null end), 2) as avg_ticket_size,
        min(transaction_date) as first_purchase_date,
        max(transaction_date) as last_purchase_date
    from transactions
    where direction = 'DEBIT'
    group by
        user_id,
        merchant_name,
        currency
)

select * from merchant_stats

