select
    cast(account_id as string)  as account_id,
    account_name,
    statement,
    pnl_line,
    cast(pnl_order as int64)    as pnl_order
from {{ source('raw', 'chart_of_accounts') }}
