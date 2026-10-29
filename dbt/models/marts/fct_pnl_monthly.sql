-- P&L de gestion mensuel consolide en EUR, reel vs budget.
-- Grain : un mois x une entite x un compte de resultat.
-- Convention de signe : produits positifs, charges negatives.
-- Conversion au taux moyen du mois (pratique usuelle pour le compte de resultat).
-- Le budget est converti au meme taux que le reel : l'ecart ne contient donc
-- pas d'effet de change, seulement l'ecart de performance.

with pnl_accounts as (
    select * from {{ ref('stg_chart_of_accounts') }}
    where statement = 'P&L'
),

actuals as (
    select
        gl.period,
        gl.entity_id,
        gl.account_id,
        sum(gl.credit_local - gl.debit_local) as actual_local
    from {{ ref('stg_gl_entries') }} gl
    inner join pnl_accounts using (account_id)
    group by 1, 2, 3
),

budget as (
    select
        b.period,
        b.entity_id,
        b.account_id,
        -- le budget est saisi en montant positif : on applique la convention de signe
        case when a.pnl_line = "Chiffre d'affaires" then b.budget_local
             else -b.budget_local end as budget_local
    from {{ ref('stg_budget') }} b
    inner join pnl_accounts a using (account_id)
),

combined as (
    select
        coalesce(a.period, b.period)            as period,
        coalesce(a.entity_id, b.entity_id)      as entity_id,
        coalesce(a.account_id, b.account_id)    as account_id,
        coalesce(a.actual_local, 0)             as actual_local,
        coalesce(b.budget_local, 0)             as budget_local
    from actuals a
    full outer join budget b
        on a.period = b.period
       and a.entity_id = b.entity_id
       and a.account_id = b.account_id
),

avg_rates as (
    select period, currency, rate
    from {{ ref('stg_fx_rates') }}
    where rate_type = 'average'
)

select
    c.period,
    parse_date('%Y-%m', c.period)                       as period_date,
    c.entity_id,
    e.entity_name,
    e.country,
    e.currency,
    c.account_id,
    acc.account_name,
    acc.pnl_line,
    acc.pnl_order,
    c.actual_local,
    c.budget_local,
    fx.rate                                             as fx_avg_rate,
    round(c.actual_local / fx.rate, 2)                  as actual_eur,
    round(c.budget_local / fx.rate, 2)                  as budget_eur,
    round((c.actual_local - c.budget_local) / fx.rate, 2) as variance_eur
from combined c
inner join {{ ref('stg_entities') }} e using (entity_id)
inner join pnl_accounts acc using (account_id)
left join avg_rates fx
    on fx.period = c.period
   and fx.currency = e.currency
