from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import database_needs_ssl, get_settings

settings = get_settings()

_engine_kwargs: dict = {
    "echo": settings.debug,
    "pool_pre_ping": True,
}
if database_needs_ssl(settings.database_url):
    _engine_kwargs["connect_args"] = {"ssl": True}

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
