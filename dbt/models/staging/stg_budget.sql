select
    entity_id,
    cast(period as string)          as period,
    cast(account_id as string)      as account_id,
    cast(budget_local as numeric)   as budget_local
from {{ source('raw', 'budget') }}
