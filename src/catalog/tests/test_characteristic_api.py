"""Integration tests for the TMF633 ServiceSpecCharacteristic API.

Run with: pytest src/catalog/tests/test_characteristic_api.py -v

Tests cover:
  - ServiceSpecCharacteristic CRUD on a given ServiceSpecification
  - CharacteristicValueSpecification CRUD on a given characteristic
  - 404 handling for unknown spec / char / vs IDs
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db

SPEC_BASE = "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"


@pytest_asyncio.fixture
async def client(db_session):
    """Return an AsyncClient with the database dependency overridden."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def create_spec(client, name="Spec For Chars"):
    resp = await client.post(SPEC_BASE, json={"name": name, "lifecycle_status": "draft"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def char_base(spec_id: str) -> str:
    return f"{SPEC_BASE}/{spec_id}/serviceSpecCharacteristic"


def vs_base(spec_id: str, char_id: str) -> str:
    return f"{char_base(spec_id)}/{char_id}/characteristicValueSpecification"


# ══ ServiceSpecCharacteristic ══════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_characteristic_returns_201(client):
    spec = await create_spec(client)
    payload = {
        "name": "bandwidth",
        "description": "Download bandwidth",
        "value_type": "integer",
        "min_cardinality": 1,
        "max_cardinality": 1,
        "is_unique": True,
        "extensible": False,
    }
    resp = await client.post(char_base(spec["id"]), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "bandwidth"
    assert data["value_type"] == "integer"
    assert data["is_unique"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_characteristic_missing_name_returns_422(client):
    spec = await create_spec(client)
    resp = await client.post(char_base(spec["id"]), json={"value_type": "string"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_characteristic_unknown_spec_returns_404(client):
    resp = await client.post(
        char_base("00000000-0000-0000-0000-000000000000"),
        json={"name": "orphan"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_characteristics_returns_200(client):
    spec = await create_spec(client)
    await client.post(char_base(spec["id"]), json={"name": "speed"})
    await client.post(char_base(spec["id"]), json={"name": "latency"})

    resp = await client.get(char_base(spec["id"]))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert resp.headers.get("X-Total-Count") == "2"


@pytest.mark.asyncio
async def test_get_characteristic_returns_200(client):
    spec = await create_spec(client)
    created = (await client.post(char_base(spec["id"]), json={"name": "speed"})).json()

    resp = await client.get(f"{char_base(spec['id'])}/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "speed"


@pytest.mark.asyncio
async def test_get_characteristic_unknown_returns_404(client):
    spec = await create_spec(client)
    resp = await client.get(
        f"{char_base(spec['id'])}/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_characteristic_returns_200(client):
    spec = await create_spec(client)
    created = (await client.post(char_base(spec["id"]), json={"name": "speed"})).json()

    resp = await client.patch(
        f"{char_base(spec['id'])}/{created['id']}",
        json={"description": "Updated description", "max_cardinality": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "Updated description"
    assert data["max_cardinality"] == 5


@pytest.mark.asyncio
async def test_delete_characteristic_returns_204(client):
    spec = await create_spec(client)
    created = (await client.post(char_base(spec["id"]), json={"name": "temp"})).json()

    resp = await client.delete(f"{char_base(spec['id'])}/{created['id']}")
    assert resp.status_code == 204

    # Confirm it's gone
    resp2 = await client.get(f"{char_base(spec['id'])}/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_create_characteristic_with_value_specs(client):
    """POST with nested characteristicValueSpecification should persist them."""
    spec = await create_spec(client)
    payload = {
        "name": "speed_tier",
        "value_type": "string",
        "characteristic_value_specification": [
            {"value": "100Mbps", "value_type": "string", "is_default": True},
            {"value": "1Gbps", "value_type": "string"},
        ],
    }
    resp = await client.post(char_base(spec["id"]), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["characteristic_value_specification"]) == 2


# ══ CharacteristicValueSpecification ══════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_value_spec_returns_201(client):
    spec = await create_spec(client)
    char = (await client.post(char_base(spec["id"]), json={"name": "bandwidth"})).json()

    payload = {
        "value": "100Mbps",
        "value_type": "string",
        "unit_of_measure": "Mbps",
        "is_default": True,
    }
    resp = await client.post(vs_base(spec["id"], char["id"]), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["value"] == "100Mbps"
    assert data["is_default"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_list_value_specs_returns_200(client):
    spec = await create_spec(client)
    char = (await client.post(char_base(spec["id"]), json={"name": "bandwidth"})).json()
    await client.post(vs_base(spec["id"], char["id"]), json={"value": "10Mbps"})
    await client.post(vs_base(spec["id"], char["id"]), json={"value": "100Mbps"})

    resp = await client.get(vs_base(spec["id"], char["id"]))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_value_spec_returns_200(client):
    spec = await create_spec(client)
    char = (await client.post(char_base(spec["id"]), json={"name": "bandwidth"})).json()
    vs = (await client.post(vs_base(spec["id"], char["id"]), json={"value": "10Mbps"})).json()

    resp = await client.get(f"{vs_base(spec['id'], char['id'])}/{vs['id']}")
    assert resp.status_code == 200
    assert resp.json()["value"] == "10Mbps"


@pytest.mark.asyncio
async def test_get_value_spec_unknown_returns_404(client):
    spec = await create_spec(client)
    char = (await client.post(char_base(spec["id"]), json={"name": "bandwidth"})).json()

    resp = await client.get(
        f"{vs_base(spec['id'], char['id'])}/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_value_spec_returns_204(client):
    spec = await create_spec(client)
    char = (await client.post(char_base(spec["id"]), json={"name": "bandwidth"})).json()
    vs = (await client.post(vs_base(spec["id"], char["id"]), json={"value": "10Mbps"})).json()

    resp = await client.delete(f"{vs_base(spec['id'], char['id'])}/{vs['id']}")
    assert resp.status_code == 204

    # Confirm deleted
    resp2 = await client.get(f"{vs_base(spec['id'], char['id'])}/{vs['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_value_spec_scoped_to_characteristic(client):
    """Value spec cannot be fetched via a different characteristic's path."""
    spec = await create_spec(client)
    char1 = (await client.post(char_base(spec["id"]), json={"name": "char1"})).json()
    char2 = (await client.post(char_base(spec["id"]), json={"name": "char2"})).json()
    vs = (await client.post(vs_base(spec["id"], char1["id"]), json={"value": "V"})).json()

    # Try fetching through char2's path — should 404
    resp = await client.get(f"{vs_base(spec['id'], char2['id'])}/{vs['id']}")
    assert resp.status_code == 404
