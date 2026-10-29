select entity_id, entity_name, country, currency
from {{ source('raw', 'entities') }}
