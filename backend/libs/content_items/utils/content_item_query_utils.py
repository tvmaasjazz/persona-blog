from sqlalchemy import ColumnElement, and_, or_

from libs.database.orm.content_item import ContentItemOrm
from libs.database.orm.persona import PersonaOrm
from libs.database.utils import DatabaseClockUtils


class ContentItemQueryUtils:
    """Builds the WHERE conditions that decide which content items a user may see."""

    @staticmethod
    def build_accessible_condition(auth_user_id: int) -> ColumnElement[bool]:
        """Matches the user's own items and other people's published items of public personas."""
        is_published_public = and_(
            ContentItemOrm.is_public,
            ContentItemOrm.published_at.is_not(None),
            ContentItemOrm.published_at <= DatabaseClockUtils.build_utc_now_sql(),
            PersonaOrm.is_public,
        )
        return or_(ContentItemOrm.created_by_id == auth_user_id, is_published_public)

    @staticmethod
    def build_owned_condition(auth_user_id: int) -> ColumnElement[bool]:
        """Matches only the items the user created, whatever their visibility."""
        return ContentItemOrm.created_by_id == auth_user_id
