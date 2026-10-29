select
    cast(period as string)      as period,
    currency,
    rate_type,
    cast(rate as numeric)       as rate
from {{ source('raw', 'fx_rates') }}
