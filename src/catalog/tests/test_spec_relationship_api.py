"""Integration tests for the TMF633 ServiceSpecRelationship REST API.

Run with: pytest src/catalog/tests/test_spec_relationship_api.py -v

Tests cover:
    - GET  /serviceSpecification/{id}/serviceSpecRelationship
    - POST /serviceSpecification/{id}/serviceSpecRelationship
    - DELETE /serviceSpecification/{id}/serviceSpecRelationship/{rel_id}
    - Business rule: self-reference → 422
    - Business rule: unknown related spec → 404
    - Business rule: duplicate triple → 409
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


SPEC_BASE = "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"


async def _create_spec(client, name: str) -> dict:
    resp = await client.post(SPEC_BASE, json={"name": name, "lifecycle_status": "draft"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _rel_url(spec_id: str) -> str:
    return f"{SPEC_BASE}/{spec_id}/serviceSpecRelationship"


# ── GET ────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_spec_relationships_empty(client):
    spec = await _create_spec(client, "Spec A")
    resp = await client.get(_rel_url(spec["id"]))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_spec_relationships_returns_x_total_count(client):
    spec = await _create_spec(client, "Spec XTC")
    resp = await client.get(_rel_url(spec["id"]))
    assert resp.status_code == 200
    assert "x-total-count" in resp.headers


# ── POST ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_spec_relationship_returns_201(client):
    spec_a = await _create_spec(client, "CFS Spec")
    spec_b = await _create_spec(client, "RFS Spec")
    payload = {"relationship_type": "dependency", "related_spec_id": spec_b["id"]}
    resp = await client.post(_rel_url(spec_a["id"]), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["spec_id"] == spec_a["id"]
    assert data["related_spec_id"] == spec_b["id"]
    assert data["relationship_type"] == "dependency"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_spec_relationship_persists_name_auto(client):
    """Name is auto-populated from the related spec when not provided."""
    spec_a = await _create_spec(client, "Auto Name Src")
    spec_b = await _create_spec(client, "Auto Name Target")
    payload = {"relationship_type": "hasPart", "related_spec_id": spec_b["id"]}
    resp = await client.post(_rel_url(spec_a["id"]), json=payload)
    assert resp.status_code == 201
    assert resp.json()["related_spec_name"] == spec_b["name"]


@pytest.mark.asyncio
async def test_create_spec_relationship_self_ref_returns_422(client):
    """Self-reference must be rejected with 422."""
    spec = await _create_spec(client, "Self Ref Spec")
    payload = {"relationship_type": "dependency", "related_spec_id": spec["id"]}
    resp = await client.post(_rel_url(spec["id"]), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_spec_relationship_unknown_related_returns_404(client):
    """Unknown related_spec_id must return 404."""
    spec = await _create_spec(client, "Orphan Src")
    payload = {"relationship_type": "dependency", "related_spec_id": "00000000-0000-0000-0000-000000000000"}
    resp = await client.post(_rel_url(spec["id"]), json=payload)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_spec_relationship_duplicate_returns_409(client):
    """Duplicate (spec_id, related_spec_id, type) must return 409."""
    spec_a = await _create_spec(client, "Dup Src")
    spec_b = await _create_spec(client, "Dup Target")
    payload = {"relationship_type": "dependency", "related_spec_id": spec_b["id"]}
    resp1 = await client.post(_rel_url(spec_a["id"]), json=payload)
    assert resp1.status_code == 201
    resp2 = await client.post(_rel_url(spec_a["id"]), json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_create_spec_relationship_invalid_type_returns_422(client):
    """Unknown relationship_type must be rejected with 422."""
    spec_a = await _create_spec(client, "Bad Type Src")
    spec_b = await _create_spec(client, "Bad Type Target")
    payload = {"relationship_type": "invalidType", "related_spec_id": spec_b["id"]}
    resp = await client.post(_rel_url(spec_a["id"]), json=payload)
    assert resp.status_code == 422


# ── DELETE ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_spec_relationship_returns_204(client):
    spec_a = await _create_spec(client, "Del Src")
    spec_b = await _create_spec(client, "Del Target")
    payload = {"relationship_type": "dependency", "related_spec_id": spec_b["id"]}
    create_resp = await client.post(_rel_url(spec_a["id"]), json=payload)
    assert create_resp.status_code == 201
    rel_id = create_resp.json()["id"]

    del_resp = await client.delete(f"{_rel_url(spec_a['id'])}/{rel_id}")
    assert del_resp.status_code == 204

    list_resp = await client.get(_rel_url(spec_a["id"]))
    assert list_resp.status_code == 200
    assert all(r["id"] != rel_id for r in list_resp.json())


@pytest.mark.asyncio
async def test_delete_nonexistent_relationship_returns_404(client):
    spec = await _create_spec(client, "Del 404 Spec")
    resp = await client.delete(f"{_rel_url(spec['id'])}/nonexistent-id")
    assert resp.status_code == 404


# ── Reflection in GET /serviceSpecification/{id} ──────────────────────────────

@pytest.mark.asyncio
async def test_spec_response_includes_relationships(client):
    """``spec_relationships`` field must be present in the spec detail response."""
    spec_a = await _create_spec(client, "Rel Embed Src")
    spec_b = await _create_spec(client, "Rel Embed Target")
    payload = {"relationship_type": "isContainedIn", "related_spec_id": spec_b["id"]}
    await client.post(_rel_url(spec_a["id"]), json=payload)

    detail_resp = await client.get(f"{SPEC_BASE}/{spec_a['id']}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert "spec_relationships" in detail
    assert len(detail["spec_relationships"]) == 1
    assert detail["spec_relationships"][0]["relationship_type"] == "isContainedIn"
