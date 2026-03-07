"""TMF633 Service Catalog Management — ServiceSpecRelationship REST API router.

Base path:
    /tmf-api/serviceCatalogManagement/v4/serviceSpecification/{spec_id}/serviceSpecRelationship

Endpoints:
    GET    /              List all ServiceSpecRelationship entries for a specification
    POST   /              Create a new ServiceSpecRelationship
    DELETE /{rel_id}      Delete a ServiceSpecRelationship
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.schemas import (
    ServiceSpecRelationshipCreate,
    ServiceSpecRelationshipResponse,
)
from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.catalog.repositories.spec_relationship_repo import SpecRelationshipRepository
from src.catalog.services.catalog_service import CatalogService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix=(
        "/tmf-api/serviceCatalogManagement/v4"
        "/serviceSpecification/{spec_id}/serviceSpecRelationship"
    ),
    tags=["TMF633 - Service Spec Relationship"],
)


def _get_service(db: AsyncSession = Depends(get_db)) -> CatalogService:
    """Build CatalogService with spec + relationship repositories."""
    svc = CatalogService(repo=ServiceSpecificationRepository(db))
    svc._rel_repo = SpecRelationshipRepository(db)
    return svc


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceSpecRelationshipResponse],
    summary="List ServiceSpecRelationships",
    status_code=status.HTTP_200_OK,
)
async def list_spec_relationships(
    spec_id: str,
    response: Response,
    service: CatalogService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceSpecRelationshipResponse]:
    """List all ``ServiceSpecRelationship`` entries for a ServiceSpecification.

    A relationship describes a typed link from this specification to another
    (e.g. a CFS depending on an RFS, or a bundle composed of components).
    """
    items = await service.list_spec_relationships(spec_id)
    response.headers["X-Total-Count"] = str(len(items))
    response.headers["X-Result-Count"] = str(len(items))
    return items


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ServiceSpecRelationshipResponse,
    summary="Create a ServiceSpecRelationship",
    status_code=status.HTTP_201_CREATED,
)
async def create_spec_relationship(
    spec_id: str,
    data: ServiceSpecRelationshipCreate,
    service: CatalogService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceSpecRelationshipResponse:
    """Create a new ``ServiceSpecRelationship``.

    Valid ``relationship_type`` values: ``dependency``, ``isContainedIn``,
    ``isReplacedBy``, ``hasPart``.

    Returns 409 if the exact triple (spec → related_spec, type) already exists.
    Returns 422 for self-reference or invalid relationship type.
    """
    return await service.add_spec_relationship(spec_id, data)


# ── DELETE /{rel_id} ──────────────────────────────────────────────────────────

@router.delete(
    "/{rel_id}",
    summary="Delete a ServiceSpecRelationship",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_spec_relationship(
    spec_id: str,
    rel_id: str,
    service: CatalogService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceSpecRelationship`` by its UUID."""
    await service.delete_spec_relationship(spec_id, rel_id)
