from datetime import UTC, datetime

from starlette.datastructures import State

from apps.api.core.config import AppSettings
from libs.users.services import UserActivityService


async def record_user_activity(app_state: State, user_id: int) -> None:
    """Runs after the response is sent, so it opens its own session and transaction.

    A request's session is already closed by the time a background task runs.
    """
    app_settings: AppSettings = app_state.settings
    db_session_factory = app_state.db_session_factory
    async with db_session_factory() as db_session, db_session.begin():
        user_activity_service = UserActivityService(
            db_session=db_session,
            redis_client=app_state.redis_client,
            user_settings=app_settings.users,
        )
        await user_activity_service.record_activity(user_id, datetime.now(UTC))
