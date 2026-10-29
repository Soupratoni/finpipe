-- Rapprochement : le resultat en devise locale de la table finale doit egaler
-- celui du grand livre, par entite. Detecte une ligne perdue dans les jointures.
with ledger as (
    select gl.entity_id, sum(gl.credit_local - gl.debit_local) as result_local
    from {{ ref('stg_gl_entries') }} gl
    inner join {{ ref('stg_chart_of_accounts') }} a using (account_id)
    where a.statement = 'P&L'
    group by 1
),
mart as (
    select entity_id, sum(actual_local) as result_local
    from {{ ref('fct_pnl_monthly') }}
    group by 1
)
select l.entity_id, l.result_local as ledger, m.result_local as mart
from ledger l
full outer join mart m using (entity_id)
where abs(coalesce(l.result_local, 0) - coalesce(m.result_local, 0)) > 0.01
