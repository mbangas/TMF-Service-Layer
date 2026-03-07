"""Testing REST API router — TMF653 Service Test Management.

Two sub-routers are aggregated into a single ``router`` exported from this module:

    TMF653 - Service Test Specification
        GET    /tmf-api/serviceTest/v4/serviceTestSpecification
        POST   /tmf-api/serviceTest/v4/serviceTestSpecification
        GET    /tmf-api/serviceTest/v4/serviceTestSpecification/{id}
        PATCH  /tmf-api/serviceTest/v4/serviceTestSpecification/{id}
        DELETE /tmf-api/serviceTest/v4/serviceTestSpecification/{id}

    TMF653 - Service Test Management
        GET    /tmf-api/serviceTest/v4/serviceTest
        POST   /tmf-api/serviceTest/v4/serviceTest
        GET    /tmf-api/serviceTest/v4/serviceTest/{id}
        PATCH  /tmf-api/serviceTest/v4/serviceTest/{id}
        DELETE /tmf-api/serviceTest/v4/serviceTest/{id}
        POST   /tmf-api/serviceTest/v4/serviceTest/{id}/testMeasure
        GET    /tmf-api/serviceTest/v4/serviceTest/{id}/testMeasure
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.inventory.repositories.service_repo import ServiceRepository
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db
from src.testing.models.schemas import (
    ServiceTestCreate,
    ServiceTestPatch,
    ServiceTestResponse,
    ServiceTestSpecificationCreate,
    ServiceTestSpecificationPatch,
    ServiceTestSpecificationResponse,
    TestMeasureCreate,
    TestMeasureResponse,
)
from src.testing.repositories.test_repo import ServiceTestRepository
from src.testing.repositories.test_spec_repo import TestSpecificationRepository
from src.testing.services.testing_service import (
    ServiceTestService,
    TestSpecificationService,
)

# ── Dependency factories ──────────────────────────────────────────────────────


def _get_spec_service(db: AsyncSession = Depends(get_db)) -> TestSpecificationService:
    """Dependency factory — builds TestSpecificationService with its dependencies."""
    return TestSpecificationService(
        repo=TestSpecificationRepository(db),
        catalog_repo=ServiceSpecificationRepository(db),
    )


def _get_test_service(db: AsyncSession = Depends(get_db)) -> ServiceTestService:
    """Dependency factory — builds ServiceTestService with its dependencies."""
    return ServiceTestService(
        repo=ServiceTestRepository(db),
        service_repo=ServiceRepository(db),
        spec_repo=TestSpecificationRepository(db),
    )


# ── TMF653 - Service Test Specification ──────────────────────────────────────

spec_router = APIRouter(
    prefix="/tmf-api/serviceTest/v4/serviceTestSpecification",
    tags=["TMF653 - Service Test Specification"],
)


@spec_router.get(
    "",
    response_model=list[ServiceTestSpecificationResponse],
    summary="List Service Test Specifications",
    status_code=status.HTTP_200_OK,
)
async def list_specs(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by lifecycle state"),
    svc: TestSpecificationService = Depends(_get_spec_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceTestSpecificationResponse]:
    """Retrieve a paginated list of ``ServiceTestSpecification`` instances (TMF653)."""
    items, total = await svc.list_specs(offset=offset, limit=limit, state=state)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@spec_router.post(
    "",
    response_model=ServiceTestSpecificationResponse,
    summary="Create a Service Test Specification",
    status_code=status.HTTP_201_CREATED,
)
async def create_spec(
    data: ServiceTestSpecificationCreate,
    svc: TestSpecificationService = Depends(_get_spec_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceTestSpecificationResponse:
    """Create a new ``ServiceTestSpecification`` in ``active`` state (TMF653)."""
    return await svc.create_spec(data)


@spec_router.get(
    "/{spec_id}",
    response_model=ServiceTestSpecificationResponse,
    summary="Retrieve a Service Test Specification",
    status_code=status.HTTP_200_OK,
)
async def get_spec(
    spec_id: str,
    svc: TestSpecificationService = Depends(_get_spec_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceTestSpecificationResponse:
    """Retrieve a single ``ServiceTestSpecification`` by its ID (TMF653)."""
    return await svc.get_spec(spec_id)


@spec_router.patch(
    "/{spec_id}",
    response_model=ServiceTestSpecificationResponse,
    summary="Update a Service Test Specification",
    status_code=status.HTTP_200_OK,
)
async def patch_spec(
    spec_id: str,
    data: ServiceTestSpecificationPatch,
    svc: TestSpecificationService = Depends(_get_spec_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceTestSpecificationResponse:
    """Partial update / state transition of a ``ServiceTestSpecification`` (TMF653)."""
    return await svc.patch_spec(spec_id, data)


@spec_router.delete(
    "/{spec_id}",
    response_class=Response,
    summary="Delete a Service Test Specification",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_spec(
    spec_id: str,
    svc: TestSpecificationService = Depends(_get_spec_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete an ``obsolete`` ServiceTestSpecification (TMF653)."""
    await svc.delete_spec(spec_id)


# ── TMF653 - Service Test Management ─────────────────────────────────────────

test_router = APIRouter(
    prefix="/tmf-api/serviceTest/v4/serviceTest",
    tags=["TMF653 - Service Test Management"],
)


@test_router.get(
    "",
    response_model=list[ServiceTestResponse],
    summary="List Service Tests",
    status_code=status.HTTP_200_OK,
)
async def list_tests(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by lifecycle state"),
    service_id: str | None = Query(default=None, description="Filter by service instance UUID"),
    test_spec_id: str | None = Query(
        default=None, description="Filter by test specification UUID"
    ),
    svc: ServiceTestService = Depends(_get_test_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceTestResponse]:
    """Retrieve a paginated list of ``ServiceTest`` instances (TMF653)."""
    items, total = await svc.list_tests(
        offset=offset, limit=limit, state=state,
        service_id=service_id, test_spec_id=test_spec_id,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@test_router.post(
    "",
    response_model=ServiceTestResponse,
    summary="Create a Service Test",
    status_code=status.HTTP_201_CREATED,
)
async def create_test(
    data: ServiceTestCreate,
    svc: ServiceTestService = Depends(_get_test_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceTestResponse:
    """Create a new ``ServiceTest`` in ``planned`` state (TMF653).

    The target service must be in ``active`` state.
    """
    return await svc.create_test(data)


@test_router.get(
    "/{test_id}",
    response_model=ServiceTestResponse,
    summary="Retrieve a Service Test",
    status_code=status.HTTP_200_OK,
)
async def get_test(
    test_id: str,
    svc: ServiceTestService = Depends(_get_test_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceTestResponse:
    """Retrieve a single ``ServiceTest`` by its ID, including embedded measures (TMF653)."""
    return await svc.get_test(test_id)


@test_router.patch(
    "/{test_id}",
    response_model=ServiceTestResponse,
    summary="Update a Service Test",
    status_code=status.HTTP_200_OK,
)
async def patch_test(
    test_id: str,
    data: ServiceTestPatch,
    svc: ServiceTestService = Depends(_get_test_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceTestResponse:
    """Partial update / state transition of a ``ServiceTest`` (TMF653)."""
    return await svc.patch_test(test_id, data)


@test_router.delete(
    "/{test_id}",
    response_class=Response,
    summary="Delete a Service Test",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_test(
    test_id: str,
    svc: ServiceTestService = Depends(_get_test_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a terminal ``ServiceTest`` and its measures (TMF653)."""
    await svc.delete_test(test_id)


@test_router.post(
    "/{test_id}/testMeasure",
    response_model=TestMeasureResponse,
    summary="Add a Test Measure",
    status_code=status.HTTP_201_CREATED,
)
async def add_measure(
    test_id: str,
    data: TestMeasureCreate,
    svc: ServiceTestService = Depends(_get_test_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> TestMeasureResponse:
    """Record a ``TestMeasure`` on an ``inProgress`` service test (TMF653)."""
    return await svc.add_measure(test_id, data)


@test_router.get(
    "/{test_id}/testMeasure",
    response_model=list[TestMeasureResponse],
    summary="List Test Measures",
    status_code=status.HTTP_200_OK,
)
async def list_measures(
    test_id: str,
    svc: ServiceTestService = Depends(_get_test_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[TestMeasureResponse]:
    """List all ``TestMeasure`` records for a given service test (TMF653)."""
    return await svc.list_measures(test_id)


# ── Aggregate router ──────────────────────────────────────────────────────────

router = APIRouter()
router.include_router(spec_router)
router.include_router(test_router)
