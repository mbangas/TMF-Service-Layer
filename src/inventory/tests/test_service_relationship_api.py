"""Integration tests for the TMF638 ServiceRelationship REST API.

Run with: pytest src/inventory/tests/test_service_relationship_api.py -v

Tests cover:
    - GET  /service/{id}/serviceRelationship
    - POST /service/{id}/serviceRelationship
    - DELETE /service/{id}/serviceRelationship/{rel_id}
    - Business rule: self-reference → 422
    - Business rule: duplicate triple → 409
    - Business rule: unknown related_service_id → 404
    - CASCADE: deleting parent service removes its relationships
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


SVC_BASE = "/tmf-api/serviceInventory/v4/service"


async def _create_service(client, *, name="Test Service", state="active") -> dict:
    resp = await client.post(SVC_BASE, json={"name": name, "state": state})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _rel_url(service_id: str) -> str:
    return f"{SVC_BASE}/{service_id}/serviceRelationship"


# ── GET ────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_service_relationships_empty(client):
    svc = await _create_service(client, name="Empty Rel Svc")
    resp = await client.get(_rel_url(svc["id"]))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_service_relationships_returns_x_total_count(client):
    svc = await _create_service(client, name="Header Check Svc")
    resp = await client.get(_rel_url(svc["id"]))
    assert resp.status_code == 200
    assert "x-total-count" in resp.headers


# ── POST ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_service_relationship_returns_201(client):
    svc_a = await _create_service(client, name="CFS Service")
    svc_b = await _create_service(client, name="RFS Service")
    payload = {"relationship_type": "dependency", "related_service_id": svc_b["id"]}
    resp = await client.post(_rel_url(svc_a["id"]), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["service_id"] == svc_a["id"]
    assert data["related_service_id"] == svc_b["id"]
    assert data["relationship_type"] == "dependency"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_service_relationship_self_ref_returns_422(client):
    svc = await _create_service(client, name="Self Ref Svc")
    payload = {"relationship_type": "dependency", "related_service_id": svc["id"]}
    resp = await client.post(_rel_url(svc["id"]), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_service_relationship_unknown_related_returns_404(client):
    svc = await _create_service(client, name="Orphan Svc")
    payload = {"relationship_type": "dependency", "related_service_id": "00000000-0000-0000-0000-000000000000"}
    resp = await client.post(_rel_url(svc["id"]), json=payload)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_service_relationship_duplicate_returns_409(client):
    svc_a = await _create_service(client, name="Dup Src Svc")
    svc_b = await _create_service(client, name="Dup Target Svc")
    payload = {"relationship_type": "dependency", "related_service_id": svc_b["id"]}
    resp1 = await client.post(_rel_url(svc_a["id"]), json=payload)
    assert resp1.status_code == 201
    resp2 = await client.post(_rel_url(svc_a["id"]), json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_create_service_relationship_invalid_type_returns_422(client):
    svc_a = await _create_service(client, name="Bad Type Src Svc")
    svc_b = await _create_service(client, name="Bad Type Target Svc")
    payload = {"relationship_type": "notAType", "related_service_id": svc_b["id"]}
    resp = await client.post(_rel_url(svc_a["id"]), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_service_relationship_auto_populates_name(client):
    """Service name is auto-populated from the related service when not provided."""
    svc_a = await _create_service(client, name="Auto Name CFS")
    svc_b = await _create_service(client, name="Auto Name RFS")
    payload = {"relationship_type": "hasPart", "related_service_id": svc_b["id"]}
    resp = await client.post(_rel_url(svc_a["id"]), json=payload)
    assert resp.status_code == 201
    assert resp.json()["related_service_name"] == svc_b["name"]


# ── DELETE ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_service_relationship_returns_204(client):
    svc_a = await _create_service(client, name="Del Src Svc")
    svc_b = await _create_service(client, name="Del Target Svc")
    payload = {"relationship_type": "dependency", "related_service_id": svc_b["id"]}
    create_resp = await client.post(_rel_url(svc_a["id"]), json=payload)
    assert create_resp.status_code == 201
    rel_id = create_resp.json()["id"]

    del_resp = await client.delete(f"{_rel_url(svc_a['id'])}/{rel_id}")
    assert del_resp.status_code == 204

    list_resp = await client.get(_rel_url(svc_a["id"]))
    assert list_resp.status_code == 200
    assert all(r["id"] != rel_id for r in list_resp.json())


@pytest.mark.asyncio
async def test_delete_nonexistent_relationship_returns_404(client):
    svc = await _create_service(client, name="Del 404 Svc")
    resp = await client.delete(f"{_rel_url(svc['id'])}/nonexistent-rel-id")
    assert resp.status_code == 404


# ── CASCADE ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_parent_service_cascades_relationships(client):
    """Deleting a service (CASCADE) must remove its own relationships."""
    svc_a = await _create_service(client, name="Cascade Parent")
    svc_b = await _create_service(client, name="Cascade Target")
    payload = {"relationship_type": "dependency", "related_service_id": svc_b["id"]}
    await client.post(_rel_url(svc_a["id"]), json=payload)

    # Terminate and then delete svc_a
    await client.patch(f"{SVC_BASE}/{svc_a['id']}", json={"state": "terminated"})
    del_resp = await client.delete(f"{SVC_BASE}/{svc_a['id']}")
    assert del_resp.status_code == 204

    # Verify the relationship no longer exists (would 404 on the parent)
    list_resp = await client.get(_rel_url(svc_a["id"]))
    assert list_resp.status_code == 404


# ── Reflection in GET /service/{id} ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_response_includes_relationships(client):
    """``service_relationships`` field must be present in the service detail response."""
    svc_a = await _create_service(client, name="Embed Src Svc")
    svc_b = await _create_service(client, name="Embed Target Svc")
    payload = {"relationship_type": "isContainedIn", "related_service_id": svc_b["id"]}
    await client.post(_rel_url(svc_a["id"]), json=payload)

    detail_resp = await client.get(f"{SVC_BASE}/{svc_a['id']}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert "service_relationships" in detail
    assert len(detail["service_relationships"]) == 1
    assert detail["service_relationships"][0]["relationship_type"] == "isContainedIn"
