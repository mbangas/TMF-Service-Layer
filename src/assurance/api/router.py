"""Assurance REST API router — TMF642, TMF628, TMF657.

Three sub-routers are aggregated into a single ``router`` exported from this module:

    TMF642 - Alarm Management
        GET    /tmf-api/alarmManagement/v4/alarm
        POST   /tmf-api/alarmManagement/v4/alarm
        GET    /tmf-api/alarmManagement/v4/alarm/{id}
        PATCH  /tmf-api/alarmManagement/v4/alarm/{id}
        DELETE /tmf-api/alarmManagement/v4/alarm/{id}

    TMF628 - Performance Management
        GET    /tmf-api/performanceManagement/v4/performanceMeasurement
        POST   /tmf-api/performanceManagement/v4/performanceMeasurement
        GET    /tmf-api/performanceManagement/v4/performanceMeasurement/{id}
        PATCH  /tmf-api/performanceManagement/v4/performanceMeasurement/{id}
        DELETE /tmf-api/performanceManagement/v4/performanceMeasurement/{id}

    TMF657 - Service Level Management
        GET    /tmf-api/serviceLevelManagement/v4/serviceLevel
        POST   /tmf-api/serviceLevelManagement/v4/serviceLevel
        GET    /tmf-api/serviceLevelManagement/v4/serviceLevel/{id}
        PATCH  /tmf-api/serviceLevelManagement/v4/serviceLevel/{id}
        DELETE /tmf-api/serviceLevelManagement/v4/serviceLevel/{id}
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.assurance.models.schemas import (
    AlarmCreate,
    AlarmPatch,
    AlarmResponse,
    PerformanceMeasurementCreate,
    PerformanceMeasurementPatch,
    PerformanceMeasurementResponse,
    ServiceLevelObjectiveCreate,
    ServiceLevelObjectivePatch,
    ServiceLevelObjectiveResponse,
)
from src.assurance.repositories.alarm_repo import AlarmRepository
from src.assurance.repositories.measurement_repo import MeasurementRepository
from src.assurance.repositories.slo_repo import SLORepository
from src.assurance.services.assurance_service import (
    AlarmService,
    PerformanceMeasurementService,
    ServiceLevelObjectiveService,
)
from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.inventory.repositories.service_repo import ServiceRepository
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

# ── Dependency factories ───────────────────────────────────────────────────────


def _get_alarm_service(db: AsyncSession = Depends(get_db)) -> AlarmService:
    """Dependency factory — builds AlarmService with its dependencies."""
    return AlarmService(
        repo=AlarmRepository(db),
        service_repo=ServiceRepository(db),
    )


def _get_slo_service(db: AsyncSession = Depends(get_db)) -> ServiceLevelObjectiveService:
    """Dependency factory — builds ServiceLevelObjectiveService with its dependencies."""
    return ServiceLevelObjectiveService(
        repo=SLORepository(db),
        service_repo=ServiceRepository(db),
        spec_repo=ServiceSpecificationRepository(db),
    )


def _get_measurement_service(db: AsyncSession = Depends(get_db)) -> PerformanceMeasurementService:
    """Dependency factory — builds PerformanceMeasurementService with its dependencies.

    SLOService is instantiated here (not at module level) to avoid circular imports.
    """
    slo_service = ServiceLevelObjectiveService(
        repo=SLORepository(db),
        service_repo=ServiceRepository(db),
        spec_repo=ServiceSpecificationRepository(db),
    )
    return PerformanceMeasurementService(
        repo=MeasurementRepository(db),
        service_repo=ServiceRepository(db),
        slo_service=slo_service,
    )


# ── TMF642 - Alarm Management ──────────────────────────────────────────────────

alarm_router = APIRouter(
    prefix="/tmf-api/alarmManagement/v4/alarm",
    tags=["TMF642 - Alarm Management"],
)


@alarm_router.get(
    "",
    response_model=list[AlarmResponse],
    summary="List Alarms",
    status_code=status.HTTP_200_OK,
)
async def list_alarms(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by alarm state"),
    service_id: str | None = Query(default=None, description="Filter by service instance UUID"),
    svc: AlarmService = Depends(_get_alarm_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[AlarmResponse]:
    """Retrieve a paginated list of ``Alarm`` instances (TMF642 §6.1.1)."""
    items, total = await svc.list_alarms(
        offset=offset, limit=limit, state=state, service_id=service_id
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@alarm_router.post(
    "",
    response_model=AlarmResponse,
    summary="Create an Alarm",
    status_code=status.HTTP_201_CREATED,
)
async def create_alarm(
    data: AlarmCreate,
    svc: AlarmService = Depends(_get_alarm_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> AlarmResponse:
    """Create a new ``Alarm`` in ``raised`` state (TMF642 §6.1.1).

    The target service must be in ``active`` state.
    """
    return await svc.create_alarm(data)


@alarm_router.get(
    "/{alarm_id}",
    response_model=AlarmResponse,
    summary="Retrieve an Alarm",
    status_code=status.HTTP_200_OK,
)
async def get_alarm(
    alarm_id: str,
    svc: AlarmService = Depends(_get_alarm_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> AlarmResponse:
    """Retrieve a single ``Alarm`` by its ID (TMF642 §6.1.2)."""
    return await svc.get_alarm(alarm_id)


@alarm_router.patch(
    "/{alarm_id}",
    response_model=AlarmResponse,
    summary="Update an Alarm",
    status_code=status.HTTP_200_OK,
)
async def patch_alarm(
    alarm_id: str,
    data: AlarmPatch,
    svc: AlarmService = Depends(_get_alarm_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> AlarmResponse:
    """Partial update / state transition of an ``Alarm`` (TMF642 §6.1.2)."""
    return await svc.patch_alarm(alarm_id, data)


@alarm_router.delete(
    "/{alarm_id}",
    response_class=Response,
    summary="Delete an Alarm",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_alarm(
    alarm_id: str,
    svc: AlarmService = Depends(_get_alarm_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``cleared`` Alarm (TMF642 §6.1.2)."""
    await svc.delete_alarm(alarm_id)


# ── TMF628 - Performance Management ───────────────────────────────────────────

measurement_router = APIRouter(
    prefix="/tmf-api/performanceManagement/v4/performanceMeasurement",
    tags=["TMF628 - Performance Management"],
)


@measurement_router.get(
    "",
    response_model=list[PerformanceMeasurementResponse],
    summary="List PerformanceMeasurements",
    status_code=status.HTTP_200_OK,
)
async def list_measurements(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by measurement state"),
    service_id: str | None = Query(default=None, description="Filter by service instance UUID"),
    svc: PerformanceMeasurementService = Depends(_get_measurement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[PerformanceMeasurementResponse]:
    """Retrieve a paginated list of ``PerformanceMeasurement`` instances (TMF628 §6.1.1)."""
    items, total = await svc.list_measurements(
        offset=offset, limit=limit, state=state, service_id=service_id
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@measurement_router.post(
    "",
    response_model=PerformanceMeasurementResponse,
    summary="Create a PerformanceMeasurement",
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement(
    data: PerformanceMeasurementCreate,
    svc: PerformanceMeasurementService = Depends(_get_measurement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> PerformanceMeasurementResponse:
    """Create a new ``PerformanceMeasurement`` in ``scheduled`` state (TMF628 §6.1.1)."""
    return await svc.create_measurement(data)


@measurement_router.get(
    "/{measurement_id}",
    response_model=PerformanceMeasurementResponse,
    summary="Retrieve a PerformanceMeasurement",
    status_code=status.HTTP_200_OK,
)
async def get_measurement(
    measurement_id: str,
    svc: PerformanceMeasurementService = Depends(_get_measurement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> PerformanceMeasurementResponse:
    """Retrieve a single ``PerformanceMeasurement`` by its ID (TMF628 §6.1.2)."""
    return await svc.get_measurement(measurement_id)


@measurement_router.patch(
    "/{measurement_id}",
    response_model=PerformanceMeasurementResponse,
    summary="Update a PerformanceMeasurement",
    status_code=status.HTTP_200_OK,
)
async def patch_measurement(
    measurement_id: str,
    data: PerformanceMeasurementPatch,
    svc: PerformanceMeasurementService = Depends(_get_measurement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> PerformanceMeasurementResponse:
    """Partial update / state transition of a ``PerformanceMeasurement`` (TMF628 §6.1.2).

    Transitioning to ``completed`` automatically triggers SLO violation detection.
    """
    return await svc.patch_measurement(measurement_id, data)


@measurement_router.delete(
    "/{measurement_id}",
    response_class=Response,
    summary="Delete a PerformanceMeasurement",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_measurement(
    measurement_id: str,
    svc: PerformanceMeasurementService = Depends(_get_measurement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``completed`` or ``failed`` PerformanceMeasurement (TMF628 §6.1.2)."""
    await svc.delete_measurement(measurement_id)


# ── TMF657 - Service Level Management ─────────────────────────────────────────

slo_router = APIRouter(
    prefix="/tmf-api/serviceLevelManagement/v4/serviceLevel",
    tags=["TMF657 - Service Level Management"],
)


@slo_router.get(
    "",
    response_model=list[ServiceLevelObjectiveResponse],
    summary="List ServiceLevelObjectives",
    status_code=status.HTTP_200_OK,
)
async def list_slos(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by SLO state"),
    service_id: str | None = Query(default=None, description="Filter by service instance UUID"),
    svc: ServiceLevelObjectiveService = Depends(_get_slo_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceLevelObjectiveResponse]:
    """Retrieve a paginated list of ``ServiceLevelObjective`` instances (TMF657 §6.1.1)."""
    items, total = await svc.list_slos(
        offset=offset, limit=limit, state=state, service_id=service_id
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@slo_router.post(
    "",
    response_model=ServiceLevelObjectiveResponse,
    summary="Create a ServiceLevelObjective",
    status_code=status.HTTP_201_CREATED,
)
async def create_slo(
    data: ServiceLevelObjectiveCreate,
    svc: ServiceLevelObjectiveService = Depends(_get_slo_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceLevelObjectiveResponse:
    """Create a new ``ServiceLevelObjective`` in ``active`` state (TMF657 §6.1.1)."""
    return await svc.create_slo(data)


@slo_router.get(
    "/{slo_id}",
    response_model=ServiceLevelObjectiveResponse,
    summary="Retrieve a ServiceLevelObjective",
    status_code=status.HTTP_200_OK,
)
async def get_slo(
    slo_id: str,
    svc: ServiceLevelObjectiveService = Depends(_get_slo_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceLevelObjectiveResponse:
    """Retrieve a single ``ServiceLevelObjective`` by its ID (TMF657 §6.1.2)."""
    return await svc.get_slo(slo_id)


@slo_router.patch(
    "/{slo_id}",
    response_model=ServiceLevelObjectiveResponse,
    summary="Update a ServiceLevelObjective",
    status_code=status.HTTP_200_OK,
)
async def patch_slo(
    slo_id: str,
    data: ServiceLevelObjectivePatch,
    svc: ServiceLevelObjectiveService = Depends(_get_slo_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceLevelObjectiveResponse:
    """Partial update / state transition of a ``ServiceLevelObjective`` (TMF657 §6.1.2)."""
    return await svc.patch_slo(slo_id, data)


@slo_router.delete(
    "/{slo_id}",
    response_class=Response,
    summary="Delete a ServiceLevelObjective",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_slo(
    slo_id: str,
    svc: ServiceLevelObjectiveService = Depends(_get_slo_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``suspended`` ServiceLevelObjective (TMF657 §6.1.2)."""
    await svc.delete_slo(slo_id)


# ── Aggregate router ───────────────────────────────────────────────────────────

router = APIRouter()
router.include_router(alarm_router)
router.include_router(measurement_router)
router.include_router(slo_router)
