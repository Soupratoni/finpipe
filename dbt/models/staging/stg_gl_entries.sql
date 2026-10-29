-- Grand livre type et enrichi : une ligne = un mouvement comptable
select
    concat(entry_id, '-', cast(line_no as string))      as gl_line_id,
    entry_id,
    cast(line_no as int64)                              as line_no,
    entity_id,
    cast(posting_date as date)                          as posting_date,
    format_date('%Y-%m', cast(posting_date as date))    as period,
    cast(account_id as string)                          as account_id,
    cast(debit_local as numeric)                        as debit_local,
    cast(credit_local as numeric)                       as credit_local,
    currency,
    journal_code
from {{ source('raw', 'gl_entries') }}
