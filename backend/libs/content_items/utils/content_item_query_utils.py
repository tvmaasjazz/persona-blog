from sqlalchemy import ColumnElement, and_, or_, text

from libs.database.constants import UTC_NOW_SQL
from libs.database.orm.content_item import ContentItemOrm
from libs.database.orm.persona import PersonaOrm


class ContentItemQueryUtils:
    @staticmethod
    def build_accessible_condition(auth_user_id: int) -> ColumnElement[bool]:
        is_published_public = and_(
            ContentItemOrm.is_public,
            ContentItemOrm.published_at.is_not(None),
            ContentItemOrm.published_at <= text(UTC_NOW_SQL),
            PersonaOrm.is_public,
        )
        return or_(ContentItemOrm.created_by_id == auth_user_id, is_published_public)

    @staticmethod
    def build_owned_condition(auth_user_id: int) -> ColumnElement[bool]:
        return ContentItemOrm.created_by_id == auth_user_id
