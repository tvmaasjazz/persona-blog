from sqlalchemy import ColumnElement, and_, or_

from libs.database.orm.content_item import ContentItemOrm
from libs.database.orm.persona import PersonaOrm
from libs.database.utils import DatabaseClockUtils


class ContentItemQueryUtils:
    @staticmethod
    def build_accessible_condition(auth_user_id: int) -> ColumnElement[bool]:
        is_published_public = and_(
            ContentItemOrm.is_public,
            ContentItemOrm.published_at.is_not(None),
            ContentItemOrm.published_at <= DatabaseClockUtils.build_utc_now_sql(),
            PersonaOrm.is_public,
        )
        return or_(ContentItemOrm.created_by_id == auth_user_id, is_published_public)

    @staticmethod
    def build_owned_condition(auth_user_id: int) -> ColumnElement[bool]:
        return ContentItemOrm.created_by_id == auth_user_id
