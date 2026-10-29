-- Chaque couple (mois, devise) present dans le grand livre doit avoir un taux moyen.
-- Sans lui, la conversion en EUR du mois serait vide.
select distinct gl.period, gl.currency
from {{ ref('stg_gl_entries') }} gl
left join {{ ref('stg_fx_rates') }} fx
    on fx.period = gl.period
   and fx.currency = gl.currency
   and fx.rate_type = 'average'
where fx.rate is null
