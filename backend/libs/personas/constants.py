from libs.database.orm import PersonaOrm
from libs.database.pagination_config import PaginationConfig
from libs.personas.types import UserPersonaSortType

USER_PERSONA_PAGINATION_CONFIG = PaginationConfig(
    search_columns=(PersonaOrm.name,),
    sort_columns={
        UserPersonaSortType.CREATED_AT: PersonaOrm.created_at,
        UserPersonaSortType.NAME: PersonaOrm.name,
    },
    filters={},
    tiebreak_column=PersonaOrm.id,
)
