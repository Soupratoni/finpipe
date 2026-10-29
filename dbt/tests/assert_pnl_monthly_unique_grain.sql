-- Une seule ligne par mois x entite x compte dans la table finale
select period, entity_id, account_id, count(*) as nb
from {{ ref('fct_pnl_monthly') }}
group by 1, 2, 3
having count(*) > 1
