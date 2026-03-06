"""TMF640 Service Activation & Configuration — REST API router.

Base path: /tmf-api/serviceActivationConfiguration/v4/serviceActivationJob

Endpoints:
    GET    /              List all activation jobs (paginated, filterable)
    POST   /              Create a new activation job
    GET    /{id}          Retrieve a single activation job
    PATCH  /{id}          Partial update / state transition
    DELETE /{id}          Delete a job (only if failed or cancelled)
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.inventory.repositories.service_repo import ServiceRepository
from src.inventory.services.inventory_service import InventoryService
from src.provisioning.models.schemas import (
    ServiceActivationJobCreate,
    ServiceActivationJobPatch,
    ServiceActivationJobResponse,
)
from src.provisioning.repositories.activation_job_repo import ActivationJobRepository
from src.provisioning.services.provisioning_service import ProvisioningService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob",
    tags=["TMF640 - Service Activation & Configuration"],
)


def _get_provisioning_service(db: AsyncSession = Depends(get_db)) -> ProvisioningService:
    """Dependency factory — builds the ProvisioningService with its dependencies."""
    inventory_repo = ServiceRepository(db)
    inventory_svc = InventoryService(inventory_repo)
    job_repo = ActivationJobRepository(db)
    return ProvisioningService(repo=job_repo, inventory_service=inventory_svc)


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceActivationJobResponse],
    summary="List ServiceActivationJob instances",
    status_code=status.HTTP_200_OK,
)
async def list_jobs(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by job lifecycle state"),
    job_type: str | None = Query(default=None, description="Filter by job type"),
    service_id: str | None = Query(default=None, description="Filter by target service ID"),
    svc: ProvisioningService = Depends(_get_provisioning_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceActivationJobResponse]:
    """Retrieve a paginated list of ``ServiceActivationJob`` instances (TMF640 §6.1.1).

    TMF-style pagination: ``offset`` / ``limit`` query params +
    ``X-Total-Count`` and ``X-Result-Count`` response headers.
    """
    items, total = await svc.list_jobs(
        offset=offset,
        limit=limit,
        state=state,
        job_type=job_type,
        service_id=service_id,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ServiceActivationJobResponse,
    summary="Create a ServiceActivationJob",
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    data: ServiceActivationJobCreate,
    svc: ProvisioningService = Depends(_get_provisioning_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceActivationJobResponse:
    """Create a new ``ServiceActivationJob`` record (TMF640 §6.1.1).

    The job is created in ``accepted`` state. Transition to ``running``
    when processing begins, then to ``succeeded`` or ``failed``.
    """
    return await svc.create_job(data)


# ── GET /{id} ─────────────────────────────────────────────────────────────────

@router.get(
    "/{job_id}",
    response_model=ServiceActivationJobResponse,
    summary="Retrieve a ServiceActivationJob",
    status_code=status.HTTP_200_OK,
)
async def get_job(
    job_id: str,
    svc: ProvisioningService = Depends(_get_provisioning_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceActivationJobResponse:
    """Retrieve a single ``ServiceActivationJob`` by its ID (TMF640 §6.1.2).

    Raises 404 if no job with the given ID exists.
    """
    return await svc.get_job(job_id)


# ── PATCH /{id} ───────────────────────────────────────────────────────────────

@router.patch(
    "/{job_id}",
    response_model=ServiceActivationJobResponse,
    summary="Update a ServiceActivationJob",
    status_code=status.HTTP_200_OK,
)
async def patch_job(
    job_id: str,
    data: ServiceActivationJobPatch,
    svc: ProvisioningService = Depends(_get_provisioning_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceActivationJobResponse:
    """Partially update a ``ServiceActivationJob`` (TMF640 §6.1.4).

    Use the ``state`` field to drive lifecycle transitions.
    On ``succeeded``, the target Service's inventory state is automatically updated.
    Invalid transitions are rejected with 422.
    """
    return await svc.patch_job(job_id, data)


# ── DELETE /{id} ──────────────────────────────────────────────────────────────

@router.delete(
    "/{job_id}",
    summary="Delete a ServiceActivationJob",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        409: {"description": "Job is referenced by another entity"},
        422: {"description": "Job state does not permit deletion"},
    },
)
async def delete_job(
    job_id: str,
    svc: ProvisioningService = Depends(_get_provisioning_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceActivationJob`` (TMF640 §6.1.5).

    Only ``failed`` or ``cancelled`` jobs may be deleted.
    Returns 422 for any other state.
    Returns 409 if the job is referenced by another entity.
    """
    await svc.delete_job(job_id)
