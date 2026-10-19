from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from libs.database.base import SoftDeleteMixin


class SoftDeleteSession(Session):
    """Hides soft-deleted rows from every ORM select."""


@event.listens_for(SoftDeleteSession, "do_orm_execute")
def _exclude_soft_deleted_rows(orm_execute_state: ORMExecuteState) -> None:
    # Relationship and column loads inherit the criteria from the statement that started them.
    if (
        orm_execute_state.is_select
        and not orm_execute_state.is_column_load
        and not orm_execute_state.is_relationship_load
    ):
        orm_execute_state.statement = orm_execute_state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda orm_class: orm_class.deleted_at.is_(None),
                include_aliases=True,
            )
        )


def create_db_session_factory(
    db_bind: AsyncEngine | AsyncConnection,
) -> async_sessionmaker[AsyncSession]:
    """A session factory whose sessions hide soft-deleted rows and keep objects after commit."""
    return async_sessionmaker(
        bind=db_bind, expire_on_commit=False, sync_session_class=SoftDeleteSession
    )
