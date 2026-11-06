"""Rescores every content item's feed score, for use after changing an engagement weight.

Run from backend/ against the database in .env:

    uv run python -m scripts.recompute_feed_scores
"""

import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.core.config import AppSettings
from libs.content_engagement.services import ContentEngagementService
from libs.database.session import create_db_session_factory


async def _recompute_feed_scores() -> int:
    app_settings = AppSettings()
    db_engine = create_async_engine(app_settings.database_url)
    db_session_factory = create_db_session_factory(db_engine)
    try:
        async with db_session_factory() as db_session, db_session.begin():
            content_engagement_service = ContentEngagementService(
                db_session=db_session,
                content_engagement_settings=app_settings.content_engagement,
            )
            return await content_engagement_service.rescore_all_engagement()
    finally:
        await db_engine.dispose()


def main() -> int:
    """Rescores every content item and prints how many rows it rescored."""
    rescored_row_count = asyncio.run(_recompute_feed_scores())
    print(f"Rescored {rescored_row_count} content items.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
