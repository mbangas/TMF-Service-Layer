"""Integration tests for the TMF633 Service Catalog Management API.

Run with: pytest src/catalog/tests/test_catalog_api.py -v

These tests use an in-memory SQLite database (via aiosqlite) so no PostgreSQL
is required to run them locally.  The engine dialect is swapped in the
``override_get_db`` fixture below.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.catalog.models import orm  # noqa: F401 — registers ORM tables
from src.main import app
from src.shared.db.base import Base
from src.shared.db.session import get_db

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


BASE = "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"

# ── Helper ─────────────────────────────────────────────────────────────────────

async def create_spec(client, *, name="Test Spec", lifecycle_status="draft", **kwargs):
    """Create a ServiceSpecification and return the parsed JSON body."""
    payload = {"name": name, "lifecycle_status": lifecycle_status, **kwargs}
    response = await client.post(BASE, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ── POST /serviceSpecification ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_specification_returns_201(client):
    """POST should return 201 with the created resource."""
    payload = {
        "name": "Broadband Internet",
        "description": "High-speed residential broadband",
        "version": "2.0",
        "lifecycle_status": "draft",
        "is_bundle": False,
    }
    response = await client.post(BASE, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Broadband Internet"
    assert data["lifecycle_status"] == "draft"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_specification_missing_name_returns_422(client):
    """POST without a name should return 422 Unprocessable Entity."""
    response = await client.post(BASE, json={"description": "No name provided"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_spec_invalid_status_returns_422(client):
    """POST with a non-entry lifecycle status should return 422."""
    response = await client.post(
        BASE, json={"name": "Bad Status", "lifecycle_status": "retired"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_spec_with_characteristics(client):
    """POST with nested characteristics should persist them."""
    payload = {
        "name": "VPN Service",
        "service_spec_characteristic": [
            {"name": "bandwidth", "value_type": "integer", "min_cardinality": 1},
        ],
    }
    response = await client.post(BASE, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert len(data["service_spec_characteristic"]) == 1
    assert data["service_spec_characteristic"][0]["name"] == "bandwidth"


# ── GET /serviceSpecification ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_specifications_returns_200(client):
    """GET / should return 200 with a list and X-Total-Count header."""
    await create_spec(client, name="Spec A")
    await create_spec(client, name="Spec B")
    response = await client.get(BASE)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert int(response.headers.get("X-Total-Count", 0)) >= 2


@pytest.mark.asyncio
async def test_list_specifications_pagination(client):
    """offset/limit query params should be honoured."""
    for i in range(5):
        await create_spec(client, name=f"Paginated Spec {i}")
    response = await client.get(BASE, params={"offset": 0, "limit": 2})
    assert response.status_code == 200
    assert len(response.json()) <= 2


@pytest.mark.asyncio
async def test_list_specifications_filter_by_status(client):
    """lifecycle_status filter should restrict results."""
    await create_spec(client, name="Active Spec", lifecycle_status="active")
    response = await client.get(BASE, params={"lifecycle_status": "active"})
    assert response.status_code == 200
    for item in response.json():
        assert item["lifecycle_status"] == "active"


# ── GET /serviceSpecification/{id} ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_specification_by_id(client):
    """GET /{id} should return the exact resource."""
    created = await create_spec(client, name="Fetch Me")
    response = await client.get(f"{BASE}/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_nonexistent_specification_returns_404(client):
    """GET /{id} for an unknown ID should return 404."""
    response = await client.get(f"{BASE}/does-not-exist")
    assert response.status_code == 404


# ── PATCH /serviceSpecification/{id} ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_specification_name(client):
    """PATCH should update only the supplied fields."""
    created = await create_spec(client, name="Old Name")
    response = await client.patch(f"{BASE}/{created['id']}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_patch_lifecycle_valid_transition(client):
    """PATCH from draft → active should succeed."""
    created = await create_spec(client, name="Transition Test", lifecycle_status="draft")
    response = await client.patch(
        f"{BASE}/{created['id']}", json={"lifecycle_status": "active"}
    )
    assert response.status_code == 200
    assert response.json()["lifecycle_status"] == "active"


@pytest.mark.asyncio
async def test_patch_lifecycle_invalid_transition_returns_422(client):
    """PATCH from draft → retired should return 422."""
    created = await create_spec(client, name="Invalid Transition", lifecycle_status="draft")
    response = await client.patch(
        f"{BASE}/{created['id']}", json={"lifecycle_status": "retired"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_nonexistent_returns_404(client):
    """PATCH on unknown ID should return 404."""
    response = await client.patch(f"{BASE}/ghost-id", json={"name": "Ghost"})
    assert response.status_code == 404


# ── DELETE /serviceSpecification/{id} ────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_draft_specification_returns_204(client):
    """DELETE on a draft spec should return 204 No Content."""
    created = await create_spec(client, name="Delete Me")
    response = await client.delete(f"{BASE}/{created['id']}")
    assert response.status_code == 204
    # Confirm it is gone
    get_response = await client.get(f"{BASE}/{created['id']}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_active_specification_returns_422(client):
    """DELETE on an active spec should return 422 (must retire first)."""
    created = await create_spec(client, name="Active No Delete", lifecycle_status="active")
    response = await client.delete(f"{BASE}/{created['id']}")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(client):
    """DELETE on unknown ID should return 404."""
    response = await client.delete(f"{BASE}/no-such-id")
    assert response.status_code == 404
