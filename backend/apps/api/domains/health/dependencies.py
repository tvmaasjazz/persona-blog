from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine


def get_db_engine(request: Request) -> AsyncEngine:
    return request.app.state.db_engine


def get_redis_client(request: Request) -> Redis:
    return request.app.state.redis_client


DbEngineDep = Annotated[AsyncEngine, Depends(get_db_engine)]
RedisClientDep = Annotated[Redis, Depends(get_redis_client)]
