with transactions as (
    select * from {{ ref('stg_transactions') }}
),

categorized as (
    select
        user_id,
        case
            when lower(merchant_name) like '%amazon%' or lower(merchant_name) like '%flipkart%' then 'Shopping'
            when lower(merchant_name) like '%swiggy%' or lower(merchant_name) like '%zomato%' or lower(merchant_name) like '%blinkit%' or lower(merchant_name) like '%instamart%' then 'Food & Groceries'
            when lower(merchant_name) like '%uber%' or lower(merchant_name) like '%ola%' or lower(merchant_name) like '%metro%' or lower(merchant_name) like '%irctc%' then 'Travel & Commute'
            when lower(merchant_name) like '%salary%' then 'Income'
            else 'Uncategorized'
        end as spending_category,
        currency,
        amount,
        direction
    from transactions
    where direction = 'DEBIT'
),

category_summary as (
    select
        user_id,
        spending_category,
        currency,
        sum(amount) as total_spent,
        count(*) as transaction_count,
        round(avg(amount), 2) as avg_amount
    from categorized
    group by
        user_id,
        spending_category,
        currency
)

select * from category_summary

