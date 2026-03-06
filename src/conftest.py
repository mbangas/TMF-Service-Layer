"""Shared pytest fixtures for all domain modules.

Provides a common in-memory SQLite engine and per-test database session so
individual test modules do not duplicate boilerplate.  Each test module still
defines its own ``client`` fixture because the FastAPI dependency override is
trivially different per domain.

Usage in a test module::

    @pytest_asyncio.fixture
    async def client(db_session):
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
        app.dependency_overrides.clear()
"""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.catalog.models import orm as _catalog_orm  # noqa: F401 — registers ORM tables
from src.inventory.models import orm as _inventory_orm  # noqa: F401 — registers ORM tables
from src.order.models import orm as _order_orm  # noqa: F401 — registers ORM tables
from src.provisioning.models import orm as _provisioning_orm  # noqa: F401 — registers ORM tables
from src.qualification.models import orm as _qualification_orm  # noqa: F401 — registers ORM tables
from src.shared.db.base import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a single in-memory SQLite engine shared across the test session.

    All ORM modules are imported above so ``Base.metadata`` contains every
    table before ``create_all`` is called.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Yield a clean session for each test; roll back all changes after the test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
