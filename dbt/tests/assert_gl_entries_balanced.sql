-- Chaque ecriture comptable doit etre equilibree : total debit = total credit.
-- Le test echoue s'il renvoie au moins une ligne.
select
    entry_id,
    sum(debit_local)  as total_debit,
    sum(credit_local) as total_credit
from {{ ref('stg_gl_entries') }}
group by entry_id
having abs(sum(debit_local) - sum(credit_local)) > 0.01
