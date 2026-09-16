import structlog
from fastapi import APIRouter
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.api.core.dependencies import AppSettingsDep
from apps.api.domains.health.dependencies import DbEngineDep, RedisClientDep
from apps.api.domains.health.dtos import HealthResponseDto
from apps.api.domains.health.types import DependencyStatusType, HealthStatusType

logger = structlog.get_logger(__name__)

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def get_health(
    app_settings: AppSettingsDep, db_engine: DbEngineDep, redis_client: RedisClientDep
) -> HealthResponseDto:
    postgres_status = await _check_postgres(db_engine)
    redis_status = await _check_redis(redis_client)
    dependency_statuses = (postgres_status, redis_status)
    health_status = (
        HealthStatusType.OK
        if all(status == DependencyStatusType.REACHABLE for status in dependency_statuses)
        else HealthStatusType.DEGRADED
    )
    return HealthResponseDto(
        status=health_status,
        app_name=app_settings.app_name,
        environment=app_settings.environment,
        postgres=postgres_status,
        redis=redis_status,
    )


async def _check_postgres(db_engine: AsyncEngine) -> DependencyStatusType:
    try:
        async with db_engine.connect() as db_connection:
            await db_connection.execute(text("SELECT 1"))
    except (OSError, SQLAlchemyError) as error:
        logger.warning("postgres_unreachable", error=str(error))
        return DependencyStatusType.UNREACHABLE
    return DependencyStatusType.REACHABLE


async def _check_redis(redis_client: Redis) -> DependencyStatusType:
    try:
        await redis_client.ping()
    except (OSError, RedisError) as error:
        logger.warning("redis_unreachable", error=str(error))
        return DependencyStatusType.UNREACHABLE
    return DependencyStatusType.REACHABLE
