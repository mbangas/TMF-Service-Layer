"""Integration tests for TMFC006 ServiceCategory, ServiceCandidate, and
ServiceCatalog endpoints (TMF633 Service Catalog Management).

Run with: pytest src/catalog/tests/test_tmfc006_api.py -v

Uses in-memory SQLite + shared fixtures from ``src/conftest.py``.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db

BASE_CATEGORY = "/tmf-api/serviceCatalogManagement/v4/serviceCategory"
BASE_CANDIDATE = "/tmf-api/serviceCatalogManagement/v4/serviceCandidate"
BASE_CATALOG = "/tmf-api/serviceCatalogManagement/v4/serviceCatalog"
BASE_SPEC = "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"


@pytest_asyncio.fixture
async def client(db_session):
    """AsyncClient with DB dependency overridden to use the test session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def create_category(client, *, name="Test Category", lifecycle_status="active", **kwargs):
    payload = {"name": name, "lifecycle_status": lifecycle_status, **kwargs}
    response = await client.post(BASE_CATEGORY, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def create_candidate(client, *, name="Test Candidate", lifecycle_status="active", **kwargs):
    payload = {"name": name, "lifecycle_status": lifecycle_status, **kwargs}
    response = await client.post(BASE_CANDIDATE, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def create_catalog(client, *, name="Test Catalog", lifecycle_status="active", **kwargs):
    payload = {"name": name, "lifecycle_status": lifecycle_status, **kwargs}
    response = await client.post(BASE_CATALOG, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def create_spec(client, *, name="Test Spec", lifecycle_status="draft"):
    payload = {"name": name, "lifecycle_status": lifecycle_status}
    response = await client.post(BASE_SPEC, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ══════════════════════════════════════════════════════════════════════════════
# ServiceCategory tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_category_returns_201(client):
    """POST /serviceCategory should return 201 with the created resource."""
    response = await client.post(
        BASE_CATEGORY,
        json={"name": "Mobile Services", "description": "All mobile offerings"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Mobile Services"
    assert data["lifecycle_status"] == "active"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_category_missing_name_returns_422(client):
    """POST /serviceCategory without name should return 422."""
    response = await client.post(BASE_CATEGORY, json={"description": "No name"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_category_invalid_initial_status_returns_422(client):
    """POST /serviceCategory with retired initial status should return 422."""
    response = await client.post(
        BASE_CATEGORY, json={"name": "Bad Start", "lifecycle_status": "retired"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_categories_returns_200(client):
    """GET /serviceCategory should return 200 with X-Total-Count header."""
    await create_category(client, name="Cat A")
    await create_category(client, name="Cat B")
    response = await client.get(BASE_CATEGORY)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert int(response.headers.get("X-Total-Count", 0)) >= 2


@pytest.mark.asyncio
async def test_list_categories_filter_is_root(client):
    """GET /serviceCategory?is_root=true should only return root categories."""
    await create_category(client, name="Root Cat", is_root=True)
    response = await client.get(BASE_CATEGORY, params={"is_root": True})
    assert response.status_code == 200
    for item in response.json():
        assert item["is_root"] is True


@pytest.mark.asyncio
async def test_get_category_by_id(client):
    """GET /serviceCategory/{id} should return the exact resource."""
    created = await create_category(client, name="Fetch Me")
    response = await client.get(f"{BASE_CATEGORY}/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_nonexistent_category_returns_404(client):
    """GET /serviceCategory/{id} for unknown ID should return 404."""
    response = await client.get(f"{BASE_CATEGORY}/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_category_name(client):
    """PATCH /serviceCategory/{id} should update only the supplied fields."""
    created = await create_category(client, name="Old Cat Name")
    response = await client.patch(
        f"{BASE_CATEGORY}/{created['id']}", json={"name": "Updated Cat Name"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Cat Name"


@pytest.mark.asyncio
async def test_patch_category_invalid_lifecycle_transition_returns_422(client):
    """PATCH draft → retired should return 422."""
    created = await create_category(client, name="Transition Test", lifecycle_status="draft")
    response = await client.patch(
        f"{BASE_CATEGORY}/{created['id']}", json={"lifecycle_status": "retired"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_draft_category_returns_204(client):
    """DELETE on a draft category should return 204."""
    created = await create_category(client, name="Delete Me", lifecycle_status="draft")
    response = await client.delete(f"{BASE_CATEGORY}/{created['id']}")
    assert response.status_code == 204
    get_resp = await client.get(f"{BASE_CATEGORY}/{created['id']}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_active_category_returns_422(client):
    """DELETE on an active category should return 422."""
    created = await create_category(client, name="Active Cat", lifecycle_status="active")
    response = await client.delete(f"{BASE_CATEGORY}/{created['id']}")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_category_parent_child_hierarchy(client):
    """Creating a child category with parent_id should reflect in sub_categories."""
    parent = await create_category(client, name="Parent Category")
    child = await create_category(
        client, name="Child Category", parent_id=parent["id"], is_root=False
    )
    assert child["parent_id"] == parent["id"]

    # Fetch parent and verify sub_categories contains child
    parent_resp = await client.get(f"{BASE_CATEGORY}/{parent['id']}")
    assert parent_resp.status_code == 200
    sub_ids = [s["id"] for s in parent_resp.json().get("sub_categories", [])]
    assert child["id"] in sub_ids


# ══════════════════════════════════════════════════════════════════════════════
# ServiceCandidate tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_candidate_returns_201(client):
    """POST /serviceCandidate should return 201 with the created resource."""
    response = await client.post(
        BASE_CANDIDATE,
        json={"name": "Broadband Candidate", "description": "Broadband offering candidate"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Broadband Candidate"
    assert data["lifecycle_status"] == "active"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_candidate_missing_name_returns_422(client):
    """POST /serviceCandidate without name should return 422."""
    response = await client.post(BASE_CANDIDATE, json={"description": "No name"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_candidate_with_spec_ref(client):
    """POST /serviceCandidate with service_spec_id should link the spec."""
    spec = await create_spec(client, name="Linked Spec", lifecycle_status="active")
    response = await client.post(
        BASE_CANDIDATE,
        json={"name": "Linked Candidate", "service_spec_id": spec["id"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["service_specification"] is not None
    assert data["service_specification"]["id"] == spec["id"]


@pytest.mark.asyncio
async def test_create_candidate_with_categories(client):
    """POST /serviceCandidate with category_ids should associate categories."""
    cat = await create_category(client, name="VPN Category")
    response = await client.post(
        BASE_CANDIDATE,
        json={"name": "VPN Candidate", "category_ids": [cat["id"]]},
    )
    assert response.status_code == 201
    data = response.json()
    cat_ids = [c["id"] for c in data.get("categories", [])]
    assert cat["id"] in cat_ids


@pytest.mark.asyncio
async def test_list_candidates_returns_200(client):
    """GET /serviceCandidate should return 200 with X-Total-Count header."""
    await create_candidate(client, name="Candidate X")
    response = await client.get(BASE_CANDIDATE)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert int(response.headers.get("X-Total-Count", 0)) >= 1


@pytest.mark.asyncio
async def test_get_candidate_by_id(client):
    """GET /serviceCandidate/{id} should return the exact resource."""
    created = await create_candidate(client, name="Fetch Candidate")
    response = await client.get(f"{BASE_CANDIDATE}/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_nonexistent_candidate_returns_404(client):
    """GET /serviceCandidate/{id} for unknown ID should return 404."""
    response = await client.get(f"{BASE_CANDIDATE}/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_candidate_name(client):
    """PATCH /serviceCandidate/{id} should update only the supplied fields."""
    created = await create_candidate(client, name="Old Candidate Name")
    response = await client.patch(
        f"{BASE_CANDIDATE}/{created['id']}", json={"name": "New Candidate Name"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Candidate Name"


@pytest.mark.asyncio
async def test_delete_draft_candidate_returns_204(client):
    """DELETE on a draft candidate should return 204."""
    created = await create_candidate(client, name="Delete Candidate", lifecycle_status="draft")
    response = await client.delete(f"{BASE_CANDIDATE}/{created['id']}")
    assert response.status_code == 204
    get_resp = await client.get(f"{BASE_CANDIDATE}/{created['id']}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_active_candidate_returns_422(client):
    """DELETE on an active candidate should return 422."""
    created = await create_candidate(client, name="Active Candidate")
    response = await client.delete(f"{BASE_CANDIDATE}/{created['id']}")
    assert response.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# ServiceCatalog tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_catalog_returns_201(client):
    """POST /serviceCatalog should return 201 with the created resource."""
    response = await client.post(
        BASE_CATALOG,
        json={"name": "Main Service Catalog", "description": "Primary TMF catalog"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Main Service Catalog"
    assert data["lifecycle_status"] == "active"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_catalog_missing_name_returns_422(client):
    """POST /serviceCatalog without name should return 422."""
    response = await client.post(BASE_CATALOG, json={"description": "No name"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_catalog_with_categories(client):
    """POST /serviceCatalog with category_ids should associate categories."""
    cat = await create_category(client, name="Broadband Category")
    response = await client.post(
        BASE_CATALOG,
        json={"name": "Broadband Catalog", "category_ids": [cat["id"]]},
    )
    assert response.status_code == 201
    data = response.json()
    cat_ids = [c["id"] for c in data.get("categories", [])]
    assert cat["id"] in cat_ids


@pytest.mark.asyncio
async def test_list_catalogs_returns_200(client):
    """GET /serviceCatalog should return 200 with X-Total-Count header."""
    await create_catalog(client, name="List Catalog")
    response = await client.get(BASE_CATALOG)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert int(response.headers.get("X-Total-Count", 0)) >= 1


@pytest.mark.asyncio
async def test_list_catalogs_filter_by_status(client):
    """GET /serviceCatalog?lifecycle_status=active should filter results."""
    await create_catalog(client, name="Active Catalog", lifecycle_status="active")
    response = await client.get(BASE_CATALOG, params={"lifecycle_status": "active"})
    assert response.status_code == 200
    for item in response.json():
        assert item["lifecycle_status"] == "active"


@pytest.mark.asyncio
async def test_get_catalog_by_id(client):
    """GET /serviceCatalog/{id} should return the exact resource."""
    created = await create_catalog(client, name="Fetch Catalog")
    response = await client.get(f"{BASE_CATALOG}/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_nonexistent_catalog_returns_404(client):
    """GET /serviceCatalog/{id} for unknown ID should return 404."""
    response = await client.get(f"{BASE_CATALOG}/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_catalog_name(client):
    """PATCH /serviceCatalog/{id} should update only the supplied fields."""
    created = await create_catalog(client, name="Old Catalog Name")
    response = await client.patch(
        f"{BASE_CATALOG}/{created['id']}", json={"name": "New Catalog Name"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Catalog Name"


@pytest.mark.asyncio
async def test_patch_catalog_invalid_lifecycle_transition_returns_422(client):
    """PATCH active → draft should return 422."""
    created = await create_catalog(client, name="Lifecycle Test")
    response = await client.patch(
        f"{BASE_CATALOG}/{created['id']}", json={"lifecycle_status": "draft"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_draft_catalog_returns_204(client):
    """DELETE on a draft catalog should return 204."""
    created = await create_catalog(client, name="Delete Catalog", lifecycle_status="draft")
    response = await client.delete(f"{BASE_CATALOG}/{created['id']}")
    assert response.status_code == 204
    get_resp = await client.get(f"{BASE_CATALOG}/{created['id']}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_active_catalog_returns_422(client):
    """DELETE on an active catalog should return 422."""
    created = await create_catalog(client, name="Active Catalog Delete")
    response = await client.delete(f"{BASE_CATALOG}/{created['id']}")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_catalog_replaces_categories(client):
    """PUT /serviceCatalog/{id} with empty category_ids should clear categories."""
    cat = await create_category(client, name="Category To Remove")
    created = await create_catalog(
        client, name="Catalog With Cats", category_ids=[cat["id"]]
    )
    assert len(created.get("categories", [])) == 1

    response = await client.put(
        f"{BASE_CATALOG}/{created['id']}",
        json={"name": "Catalog Without Cats", "lifecycle_status": "active", "category_ids": []},
    )
    assert response.status_code == 200
    assert response.json()["categories"] == []
