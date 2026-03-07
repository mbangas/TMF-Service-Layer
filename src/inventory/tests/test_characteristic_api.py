"""Integration tests for the TMF638 ServiceCharacteristic API.

Run with: pytest src/inventory/tests/test_characteristic_api.py -v

Tests cover:
  - ServiceCharacteristic CRUD on a given Service instance
  - CharacteristicValue CRUD on a given characteristic
  - 404 handling for unknown service / char / value IDs
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db
from src.shared.events.bus import EventBus

SVC_BASE = "/tmf-api/serviceInventory/v4/service"


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


# ── Helpers ────────────────────────────────────────────────────────────────────

async def create_svc(client, name="Test Service For Chars"):
    resp = await client.post(SVC_BASE, json={"name": name, "state": "inactive"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def char_base(svc_id: str) -> str:
    return f"{SVC_BASE}/{svc_id}/serviceCharacteristic"


def val_base(svc_id: str, char_id: str) -> str:
    return f"{char_base(svc_id)}/{char_id}/characteristicValue"


# ══ ServiceCharacteristic ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_service_characteristic_returns_201(client):
    svc = await create_svc(client)
    payload = {
        "name": "speed",
        "value_type": "integer",
        "alias": "dl_speed",
        "unit_of_measure": "Mbps",
    }
    resp = await client.post(char_base(svc["id"]), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "speed"
    assert data["value_type"] == "integer"
    assert data["alias"] == "dl_speed"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_service_characteristic_missing_name_returns_422(client):
    svc = await create_svc(client)
    resp = await client.post(char_base(svc["id"]), json={"value_type": "string"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_characteristic_unknown_service_returns_404(client):
    resp = await client.post(
        char_base("00000000-0000-0000-0000-000000000000"),
        json={"name": "orphan"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_service_characteristics_returns_200(client):
    svc = await create_svc(client)
    await client.post(char_base(svc["id"]), json={"name": "speed"})
    await client.post(char_base(svc["id"]), json={"name": "latency"})

    resp = await client.get(char_base(svc["id"]))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert resp.headers.get("X-Total-Count") == "2"


@pytest.mark.asyncio
async def test_get_service_characteristic_returns_200(client):
    svc = await create_svc(client)
    created = (await client.post(char_base(svc["id"]), json={"name": "speed"})).json()

    resp = await client.get(f"{char_base(svc['id'])}/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "speed"


@pytest.mark.asyncio
async def test_get_characteristic_unknown_returns_404(client):
    svc = await create_svc(client)
    resp = await client.get(
        f"{char_base(svc['id'])}/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_service_characteristic_returns_200(client):
    svc = await create_svc(client)
    created = (await client.post(char_base(svc["id"]), json={"name": "speed"})).json()

    resp = await client.patch(
        f"{char_base(svc['id'])}/{created['id']}",
        json={"unit_of_measure": "Kbps", "alias": "updated_alias"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_of_measure"] == "Kbps"
    assert data["alias"] == "updated_alias"


@pytest.mark.asyncio
async def test_delete_service_characteristic_returns_204(client):
    svc = await create_svc(client)
    created = (await client.post(char_base(svc["id"]), json={"name": "temp"})).json()

    resp = await client.delete(f"{char_base(svc['id'])}/{created['id']}")
    assert resp.status_code == 204

    # Confirm it's gone
    resp2 = await client.get(f"{char_base(svc['id'])}/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_create_characteristic_with_values(client):
    """POST with nested characteristicValue should persist them."""
    svc = await create_svc(client)
    payload = {
        "name": "state_flag",
        "value_type": "boolean",
        "characteristic_value": [
            {"value": "true", "value_type": "boolean"},
            {"value": "false", "value_type": "boolean"},
        ],
    }
    resp = await client.post(char_base(svc["id"]), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["characteristic_value"]) == 2


# ══ CharacteristicValue ════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_characteristic_value_returns_201(client):
    svc = await create_svc(client)
    char = (await client.post(char_base(svc["id"]), json={"name": "speed"})).json()

    payload = {
        "value": "100",
        "value_type": "integer",
        "unit_of_measure": "Mbps",
    }
    resp = await client.post(val_base(svc["id"], char["id"]), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["value"] == "100"
    assert data["unit_of_measure"] == "Mbps"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_characteristic_values_returns_200(client):
    svc = await create_svc(client)
    char = (await client.post(char_base(svc["id"]), json={"name": "speed"})).json()
    await client.post(val_base(svc["id"], char["id"]), json={"value": "10"})
    await client.post(val_base(svc["id"], char["id"]), json={"value": "100"})

    resp = await client.get(val_base(svc["id"], char["id"]))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_characteristic_value_returns_200(client):
    svc = await create_svc(client)
    char = (await client.post(char_base(svc["id"]), json={"name": "speed"})).json()
    val = (await client.post(val_base(svc["id"], char["id"]), json={"value": "10"})).json()

    resp = await client.get(f"{val_base(svc['id'], char['id'])}/{val['id']}")
    assert resp.status_code == 200
    assert resp.json()["value"] == "10"


@pytest.mark.asyncio
async def test_get_characteristic_value_unknown_returns_404(client):
    svc = await create_svc(client)
    char = (await client.post(char_base(svc["id"]), json={"name": "speed"})).json()

    resp = await client.get(
        f"{val_base(svc['id'], char['id'])}/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_characteristic_value_returns_204(client):
    svc = await create_svc(client)
    char = (await client.post(char_base(svc["id"]), json={"name": "speed"})).json()
    val = (await client.post(val_base(svc["id"], char["id"]), json={"value": "10"})).json()

    resp = await client.delete(f"{val_base(svc['id'], char['id'])}/{val['id']}")
    assert resp.status_code == 204

    # Confirm deleted
    resp2 = await client.get(f"{val_base(svc['id'], char['id'])}/{val['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_characteristic_value_scoped_to_characteristic(client):
    """A value cannot be accessed via a different characteristic's path."""
    svc = await create_svc(client)
    char1 = (await client.post(char_base(svc["id"]), json={"name": "c1"})).json()
    char2 = (await client.post(char_base(svc["id"]), json={"name": "c2"})).json()
    val = (await client.post(val_base(svc["id"], char1["id"]), json={"value": "X"})).json()

    # Try fetching through char2's path — should 404
    resp = await client.get(f"{val_base(svc['id'], char2['id'])}/{val['id']}")
    assert resp.status_code == 404
