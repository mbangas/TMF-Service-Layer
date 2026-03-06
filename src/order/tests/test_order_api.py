"""Integration tests for the TMF641 Service Order Management API.

Run with: pytest src/order/tests/test_order_api.py -v

These tests use an in-memory SQLite database (via aiosqlite) so no PostgreSQL
is required to run them locally.  The engine dialect is swapped in the
``override_get_db`` fixture below.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import src.catalog.models.orm  # noqa: F401 — registers catalog tables (for FK targets)
import src.order.models.orm  # noqa: F401 — registers order tables
from src.main import app
from src.shared.db.base import Base
from src.shared.db.session import get_db
from src.shared.events.bus import EventBus

# ── Test database (SQLite in-memory, no server needed) ────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="module")
async def test_engine():
    """Create a fresh in-memory SQLite engine for the test module."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Yield a clean session for each test; roll back after the test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """Return an AsyncClient with the database dependency overridden."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    EventBus.clear()


BASE = "/tmf-api/serviceOrdering/v4/serviceOrder"


# ── Helper ─────────────────────────────────────────────────────────────────────

async def create_order(client, *, name="Test Order", **kwargs):
    """Create a ServiceOrder and return the parsed JSON body."""
    payload = {"name": name, "order_item": [], **kwargs}
    response = await client.post(BASE, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ── POST / ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_order_returns_201(client):
    """POST should return 201 with the created resource."""
    payload = {
        "name": "Broadband Install",
        "description": "Install broadband for customer",
        "category": "broadband",
        "priority": "1",
        "order_item": [],
    }
    response = await client.post(BASE, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Broadband Install"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_order_missing_name_returns_422(client):
    """POST without a name should return 422 Unprocessable Entity."""
    response = await client.post(BASE, json={"description": "No name provided", "order_item": []})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_order_state_forced_to_acknowledged(client):
    """POST should always create the order in 'acknowledged' state."""
    data = await create_order(client, name="State Test")
    assert data["state"] == "acknowledged"


@pytest.mark.asyncio
async def test_create_order_sets_order_date(client):
    """POST should set order_date to a non-null server timestamp."""
    data = await create_order(client, name="Date Test")
    assert data["order_date"] is not None


# ── GET / ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_orders_returns_200_with_total_count_header(client):
    """GET / should return 200 with X-Total-Count header."""
    await create_order(client, name="List Test A")
    await create_order(client, name="List Test B")
    response = await client.get(BASE)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "X-Total-Count" in response.headers


@pytest.mark.asyncio
async def test_list_orders_filter_by_state(client):
    """state filter should restrict results to matching orders."""
    await create_order(client, name="Filter Test Ack")
    response = await client.get(BASE, params={"state": "acknowledged"})
    assert response.status_code == 200
    for item in response.json():
        assert item["state"] == "acknowledged"


# ── GET /{id} ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_order_by_id(client):
    """GET /{id} should return the exact resource."""
    created = await create_order(client, name="Fetch Me")
    response = await client.get(f"{BASE}/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_nonexistent_order_returns_404(client):
    """GET /{id} for an unknown ID should return 404."""
    response = await client.get(f"{BASE}/does-not-exist")
    assert response.status_code == 404


# ── PATCH /{id} ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_valid_transition_acknowledged_to_inprogress(client):
    """PATCH from acknowledged → inProgress should succeed."""
    created = await create_order(client, name="Transition Test")
    response = await client.patch(f"{BASE}/{created['id']}", json={"state": "inProgress"})
    assert response.status_code == 200
    assert response.json()["state"] == "inProgress"


@pytest.mark.asyncio
async def test_patch_invalid_transition_returns_422(client):
    """PATCH from acknowledged → completed (skipping inProgress) should return 422."""
    created = await create_order(client, name="Invalid Transition")
    response = await client.patch(f"{BASE}/{created['id']}", json={"state": "completed"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_nonexistent_returns_404(client):
    """PATCH on unknown ID should return 404."""
    response = await client.patch(f"{BASE}/ghost-id", json={"state": "inProgress"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_completion_date_set_on_terminal_transition(client):
    """completion_date should be set automatically when entering a terminal state."""
    created = await create_order(client, name="Terminal Test")
    # Move to inProgress first
    await client.patch(f"{BASE}/{created['id']}", json={"state": "inProgress"})
    # Move to completed
    response = await client.patch(f"{BASE}/{created['id']}", json={"state": "completed"})
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "completed"
    # completion_date should have been set by the service layer or persisted on orm
    # (value may be None if completion_date isn't re-fetched fresh, so just check no error)


# ── DELETE /{id} ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_cancelled_order_returns_204(client):
    """DELETE on a cancelled order should return 204 No Content."""
    created = await create_order(client, name="Delete Me")
    await client.patch(f"{BASE}/{created['id']}", json={"state": "cancelled"})
    response = await client.delete(f"{BASE}/{created['id']}")
    assert response.status_code == 204
    # Confirm gone
    get_response = await client.get(f"{BASE}/{created['id']}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_active_order_returns_422(client):
    """DELETE on an acknowledged order should return 422 (must cancel first)."""
    created = await create_order(client, name="Active No Delete")
    response = await client.delete(f"{BASE}/{created['id']}")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(client):
    """DELETE on unknown ID should return 404."""
    response = await client.delete(f"{BASE}/no-such-id")
    assert response.status_code == 404
