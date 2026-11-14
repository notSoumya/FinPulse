with transactions as (
    select * from {{ ref('stg_transactions') }}
),

monthly_aggregates as (
    select
        user_id,
        transaction_month,
        currency,
        coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0) as monthly_expenses,
        coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0) as monthly_income,
        coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0)
            - coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0) as net_savings,
        case
            when coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0) > 0 then
                round(
                    (coalesce(sum(case when direction = 'CREDIT' then amount else 0 end), 0)
                    - coalesce(sum(case when direction = 'DEBIT' then amount else 0 end), 0))
                    / sum(case when direction = 'CREDIT' then amount else 0 end) * 100,
                    2
                )
            else 0.00
        end as savings_rate_pct,
        count(*) as total_transactions
    from transactions
    group by
        user_id,
        transaction_month,
        currency
)

select * from monthly_aggregates

