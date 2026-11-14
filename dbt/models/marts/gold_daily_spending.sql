with daily as (
    select * from {{ ref('int_daily_transactions') }}
),

pivoted as (
    select
        user_id,
        transaction_date,
        currency,
        coalesce(sum(case when direction = 'DEBIT' then total_amount else 0 end), 0) as total_debit_amount,
        coalesce(sum(case when direction = 'CREDIT' then total_amount else 0 end), 0) as total_credit_amount,
        coalesce(sum(case when direction = 'CREDIT' then total_amount else 0 end), 0)
            - coalesce(sum(case when direction = 'DEBIT' then total_amount else 0 end), 0) as net_cash_flow,
        coalesce(sum(case when direction = 'DEBIT' then transaction_count else 0 end), 0) as debit_count,
        coalesce(sum(case when direction = 'CREDIT' then transaction_count else 0 end), 0) as credit_count,
        sum(transaction_count) as total_transactions
    from daily
    group by
        user_id,
        transaction_date,
        currency
)

select * from pivoted

