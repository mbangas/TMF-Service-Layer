"""Integration tests for the TMF641 ServiceOrderItemRelationship REST API.

Run with: pytest src/order/tests/test_order_item_relationship_api.py -v

Tests cover:
    - GET  /serviceOrder/{id}/serviceOrderItem/{item_id}/serviceOrderItemRelationship
    - POST /serviceOrder/{id}/serviceOrderItem/{item_id}/serviceOrderItemRelationship
    - DELETE /…/{rel_id}
    - Business rule: self-reference (same label) → 422
    - Business rule: related label not found in order → 422
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


ORDER_BASE = "/tmf-api/serviceOrdering/v4/serviceOrder"


async def _create_order(client, *, name="Test Order", items=None) -> dict:
    """Create a ServiceOrder with the given order items."""
    payload: dict = {"name": name}
    if items:
        payload["order_item"] = items
    resp = await client.post(ORDER_BASE, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _rel_url(order_id: str, item_id: str) -> str:
    return f"{ORDER_BASE}/{order_id}/serviceOrderItem/{item_id}/serviceOrderItemRelationship"


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _setup_order_with_two_items(client) -> tuple[dict, dict, dict]:
    """Create an order with two items; return (order, item1, item2)."""
    order = await _create_order(client, name="Two-Item Order", items=[
        {"order_item_id": "1", "action": "add", "service_spec_name": "CFS A"},
        {"order_item_id": "2", "action": "add", "service_spec_name": "RFS B"},
    ])
    items = order.get("order_item", [])
    # items should be sorted by order_item_id label
    item1 = next(i for i in items if i["order_item_id"] == "1")
    item2 = next(i for i in items if i["order_item_id"] == "2")
    return order, item1, item2


# ── GET ────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_item_relationships_empty(client):
    order, item1, _ = await _setup_order_with_two_items(client)
    resp = await client.get(_rel_url(order["id"], item1["id"]))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_item_relationships_returns_x_total_count(client):
    order, item1, _ = await _setup_order_with_two_items(client)
    resp = await client.get(_rel_url(order["id"], item1["id"]))
    assert resp.status_code == 200
    assert "x-total-count" in resp.headers


# ── POST ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_item_relationship_returns_201(client):
    order, item2, item1 = await _setup_order_with_two_items(client)
    # item2 depends on item1
    payload = {"relationship_type": "dependency", "related_item_label": item1["order_item_id"]}
    resp = await client.post(_rel_url(order["id"], item2["id"]), json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["order_item_orm_id"] == item2["id"]
    assert data["related_item_label"] == item1["order_item_id"]
    assert data["relationship_type"] == "dependency"


@pytest.mark.asyncio
async def test_create_item_relationship_self_ref_returns_422(client):
    """Item cannot reference its own label as a dependency."""
    order, item1, _ = await _setup_order_with_two_items(client)
    payload = {"relationship_type": "dependency", "related_item_label": item1["order_item_id"]}
    resp = await client.post(_rel_url(order["id"], item1["id"]), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_item_relationship_invalid_label_returns_422(client):
    """related_item_label that does not exist in the order must be rejected."""
    order, item1, _ = await _setup_order_with_two_items(client)
    payload = {"relationship_type": "dependency", "related_item_label": "999"}
    resp = await client.post(_rel_url(order["id"], item1["id"]), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_item_relationship_invalid_type_returns_422(client):
    order, item1, item2 = await _setup_order_with_two_items(client)
    payload = {"relationship_type": "unknownType", "related_item_label": item2["order_item_id"]}
    resp = await client.post(_rel_url(order["id"], item1["id"]), json=payload)
    assert resp.status_code == 422


# ── DELETE ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_item_relationship_returns_204(client):
    order, item2, item1 = await _setup_order_with_two_items(client)
    payload = {"relationship_type": "dependency", "related_item_label": item1["order_item_id"]}
    create_resp = await client.post(_rel_url(order["id"], item2["id"]), json=payload)
    assert create_resp.status_code == 201
    rel_id = create_resp.json()["id"]

    del_resp = await client.delete(f"{_rel_url(order['id'], item2['id'])}/{rel_id}")
    assert del_resp.status_code == 204

    list_resp = await client.get(_rel_url(order["id"], item2["id"]))
    assert list_resp.status_code == 200
    assert all(r["id"] != rel_id for r in list_resp.json())


@pytest.mark.asyncio
async def test_delete_nonexistent_item_relationship_returns_404(client):
    order, item1, _ = await _setup_order_with_two_items(client)
    resp = await client.delete(f"{_rel_url(order['id'], item1['id'])}/nonexistent-rel-id")
    assert resp.status_code == 404
