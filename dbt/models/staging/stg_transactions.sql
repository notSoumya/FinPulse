with source as (
    select * from {{ source('silver', 'transactions') }}
),

renamed as (
    select
        transaction_id,
        user_id,
        cast(amount as decimal(18, 2)) as amount,
        upper(trim(currency)) as currency,
        direction,
        transaction_timestamp,
        cast(transaction_timestamp as date) as transaction_date,
        date_trunc('month', transaction_timestamp) as transaction_month,
        coalesce(nullif(trim(merchant_normalized), ''), nullif(trim(merchant_raw), ''), 'Unknown') as merchant_name,
        merchant_raw,
        merchant_normalized,
        reference_id,
        source_type,
        deduplication_key,
        processed_at
    from source
)

select * from renamed

