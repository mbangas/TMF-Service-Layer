"""Unit tests for Assurance service layer — AlarmService, PerformanceMeasurementService,
ServiceLevelObjectiveService.

These tests mock the repository and dependent service layers, so no database
connection is required.

Run with: pytest src/assurance/tests/test_assurance_service.py -v
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.assurance.models.orm import (
    AlarmOrm,
    PerformanceMeasurementOrm,
    ServiceLevelObjectiveOrm,
)
from src.assurance.models.schemas import (
    AlarmCreate,
    AlarmPatch,
    PerformanceMeasurementCreate,
    PerformanceMeasurementPatch,
    ServiceLevelObjectiveCreate,
    ServiceLevelObjectivePatch,
)
from src.assurance.repositories.alarm_repo import AlarmRepository
from src.assurance.repositories.measurement_repo import MeasurementRepository
from src.assurance.repositories.slo_repo import SLORepository
from src.assurance.services.assurance_service import (
    AlarmService,
    PerformanceMeasurementService,
    ServiceLevelObjectiveService,
    _validate_state_transition,
)
from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.inventory.models.orm import ServiceOrm
from src.inventory.repositories.service_repo import ServiceRepository
from src.shared.events.bus import EventBus


# ── ORM helpers ────────────────────────────────────────────────────────────────

def make_service_orm(service_id: str = "svc-id", state: str = "active") -> ServiceOrm:
    """Build a minimal ServiceOrm for testing."""
    return ServiceOrm(id=service_id, name="Test Service", state=state)


def make_alarm_orm(
    alarm_id: str = "alarm-id",
    state: str = "raised",
    service_id: str = "svc-id",
) -> AlarmOrm:
    """Build a minimal AlarmOrm for testing."""
    return AlarmOrm(
        id=alarm_id,
        href=f"/tmf-api/alarmManagement/v4/alarm/{alarm_id}",
        name="Test Alarm",
        state=state,
        service_id=service_id,
    )


def make_measurement_orm(
    measurement_id: str = "m-id",
    state: str = "scheduled",
    metric_name: str = "latency_ms",
    metric_value: float | None = None,
    service_id: str = "svc-id",
) -> PerformanceMeasurementOrm:
    """Build a minimal PerformanceMeasurementOrm for testing."""
    return PerformanceMeasurementOrm(
        id=measurement_id,
        href=f"/tmf-api/performanceManagement/v4/performanceMeasurement/{measurement_id}",
        name="Test Measurement",
        state=state,
        metric_name=metric_name,
        metric_value=metric_value,
        service_id=service_id,
    )


def make_slo_orm(
    slo_id: str = "slo-id",
    state: str = "active",
    metric_name: str = "latency_ms",
    threshold_value: float | None = 100.0,
    direction: str | None = "above",
    service_id: str = "svc-id",
) -> ServiceLevelObjectiveOrm:
    """Build a minimal ServiceLevelObjectiveOrm for testing."""
    return ServiceLevelObjectiveOrm(
        id=slo_id,
        href=f"/tmf-api/serviceLevelManagement/v4/serviceLevel/{slo_id}",
        name="Test SLO",
        state=state,
        metric_name=metric_name,
        threshold_value=threshold_value,
        direction=direction,
        service_id=service_id,
    )


# ── _validate_state_transition ─────────────────────────────────────────────────

def test_validate_state_transition_valid():
    """Valid transition should not raise."""
    from src.assurance.models.schemas import ALARM_TRANSITIONS
    _validate_state_transition("raised", "acknowledged", ALARM_TRANSITIONS, "alarm")


def test_validate_state_transition_invalid_raises_422():
    """Invalid transition should raise HTTP 422."""
    from src.assurance.models.schemas import ALARM_TRANSITIONS
    with pytest.raises(HTTPException) as exc_info:
        _validate_state_transition("raised", "cleared", ALARM_TRANSITIONS, "alarm")
    assert exc_info.value.status_code == 422
    assert "raised" in exc_info.value.detail
    assert "cleared" in exc_info.value.detail


def test_validate_state_transition_terminal_state_raises_422():
    """Transitioning from a terminal state should raise HTTP 422."""
    from src.assurance.models.schemas import ALARM_TRANSITIONS
    with pytest.raises(HTTPException) as exc_info:
        _validate_state_transition("cleared", "raised", ALARM_TRANSITIONS, "alarm")
    assert exc_info.value.status_code == 422
    assert "terminal" in exc_info.value.detail.lower()


def test_validate_measurement_transitions_valid():
    """Measurement: scheduled→completed and scheduled→failed are valid."""
    from src.assurance.models.schemas import MEASUREMENT_TRANSITIONS
    _validate_state_transition("scheduled", "completed", MEASUREMENT_TRANSITIONS, "measurement")
    _validate_state_transition("scheduled", "failed", MEASUREMENT_TRANSITIONS, "measurement")


def test_validate_slo_transitions_valid():
    """SLO: active→suspended, violated→active, violated→suspended, suspended→active."""
    from src.assurance.models.schemas import SLO_TRANSITIONS
    _validate_state_transition("active", "suspended", SLO_TRANSITIONS, "SLO")
    _validate_state_transition("violated", "active", SLO_TRANSITIONS, "SLO")
    _validate_state_transition("violated", "suspended", SLO_TRANSITIONS, "SLO")
    _validate_state_transition("suspended", "active", SLO_TRANSITIONS, "SLO")


def test_validate_slo_active_to_violated_invalid():
    """SLO: active→violated via PATCH is NOT allowed (only via check_violations)."""
    from src.assurance.models.schemas import SLO_TRANSITIONS
    with pytest.raises(HTTPException) as exc_info:
        _validate_state_transition("active", "violated", SLO_TRANSITIONS, "SLO")
    assert exc_info.value.status_code == 422


# ── AlarmService ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_alarm_inactive_service_raises_422():
    """create_alarm with an inactive service should raise 422."""
    alarm_repo = MagicMock(spec=AlarmRepository)
    service_repo = MagicMock(spec=ServiceRepository)
    service_repo.get_by_id = AsyncMock(return_value=make_service_orm(state="inactive"))

    svc = AlarmService(repo=alarm_repo, service_repo=service_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_alarm(
            AlarmCreate(name="Test Alarm", service_id="svc-id")
        )
    assert exc_info.value.status_code == 422
    assert "active" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_create_alarm_service_not_found_raises_404():
    """create_alarm with a non-existent service should raise 404."""
    alarm_repo = MagicMock(spec=AlarmRepository)
    service_repo = MagicMock(spec=ServiceRepository)
    service_repo.get_by_id = AsyncMock(return_value=None)

    svc = AlarmService(repo=alarm_repo, service_repo=service_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_alarm(AlarmCreate(name="Test Alarm", service_id="ghost"))
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_alarm_publishes_create_event():
    """create_alarm should publish exactly one AlarmCreateEvent."""
    alarm_orm = make_alarm_orm()
    alarm_repo = MagicMock(spec=AlarmRepository)
    alarm_repo.create = AsyncMock(return_value=alarm_orm)
    service_repo = MagicMock(spec=ServiceRepository)
    service_repo.get_by_id = AsyncMock(return_value=make_service_orm(state="active"))

    svc = AlarmService(repo=alarm_repo, service_repo=service_repo)
    EventBus.clear()
    await svc.create_alarm(AlarmCreate(name="Test Alarm", service_id="svc-id"))

    events = EventBus.get_events(10)
    assert any(e.event_type == "AlarmCreateEvent" for e in events)


@pytest.mark.asyncio
async def test_delete_alarm_not_in_deletable_state_raises_422():
    """delete_alarm in 'raised' state should raise 422."""
    alarm_orm = make_alarm_orm(state="raised")
    alarm_repo = MagicMock(spec=AlarmRepository)
    alarm_repo.get_by_id = AsyncMock(return_value=alarm_orm)

    svc = AlarmService(repo=alarm_repo, service_repo=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_alarm("alarm-id")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_patch_alarm_state_change_publishes_event():
    """patch_alarm with a state change should publish AlarmStateChangeEvent."""
    alarm_orm = make_alarm_orm(state="raised")
    patched_orm = make_alarm_orm(state="acknowledged")
    alarm_repo = MagicMock(spec=AlarmRepository)
    alarm_repo.get_by_id = AsyncMock(return_value=alarm_orm)
    alarm_repo.patch = AsyncMock(return_value=patched_orm)

    svc = AlarmService(repo=alarm_repo, service_repo=MagicMock())
    EventBus.clear()
    await svc.patch_alarm("alarm-id", AlarmPatch(state="acknowledged"))

    events = EventBus.get_events(10)
    assert any(e.event_type == "AlarmStateChangeEvent" for e in events)


# ── ServiceLevelObjectiveService.check_violations ─────────────────────────────

@pytest.mark.asyncio
async def test_check_violations_above_direction_triggers_violation():
    """check_violations: value > threshold (direction=above) should violate the SLO."""
    slo_orm = make_slo_orm(threshold_value=100.0, direction="above")

    mock_db = AsyncMock()
    slo_repo = MagicMock(spec=SLORepository)
    slo_repo._db = mock_db
    slo_repo.get_active_by_service_and_metric = AsyncMock(return_value=[slo_orm])

    svc = ServiceLevelObjectiveService(
        repo=slo_repo,
        service_repo=MagicMock(),
        spec_repo=MagicMock(),
    )
    EventBus.clear()
    await svc.check_violations("svc-id", "latency_ms", 150.0)

    assert slo_orm.state == "violated"
    events = EventBus.get_events(10)
    assert any(e.event_type == "ServiceLevelObjectiveViolationEvent" for e in events)


@pytest.mark.asyncio
async def test_check_violations_above_direction_no_breach():
    """check_violations: value <= threshold (direction=above) should NOT violate."""
    slo_orm = make_slo_orm(threshold_value=100.0, direction="above")

    slo_repo = MagicMock(spec=SLORepository)
    slo_repo.get_active_by_service_and_metric = AsyncMock(return_value=[slo_orm])

    svc = ServiceLevelObjectiveService(
        repo=slo_repo,
        service_repo=MagicMock(),
        spec_repo=MagicMock(),
    )
    EventBus.clear()
    await svc.check_violations("svc-id", "latency_ms", 80.0)

    assert slo_orm.state == "active"
    events = EventBus.get_events(10)
    assert not any(e.event_type == "ServiceLevelObjectiveViolationEvent" for e in events)


@pytest.mark.asyncio
async def test_check_violations_below_direction_triggers_violation():
    """check_violations: value < threshold (direction=below) should violate the SLO."""
    slo_orm = make_slo_orm(threshold_value=99.5, direction="below")

    mock_db = AsyncMock()
    slo_repo = MagicMock(spec=SLORepository)
    slo_repo._db = mock_db
    slo_repo.get_active_by_service_and_metric = AsyncMock(return_value=[slo_orm])

    svc = ServiceLevelObjectiveService(
        repo=slo_repo,
        service_repo=MagicMock(),
        spec_repo=MagicMock(),
    )
    EventBus.clear()
    await svc.check_violations("svc-id", "availability_pct", 98.0)

    assert slo_orm.state == "violated"
    events = EventBus.get_events(10)
    assert any(e.event_type == "ServiceLevelObjectiveViolationEvent" for e in events)


@pytest.mark.asyncio
async def test_check_violations_below_direction_no_breach():
    """check_violations: value >= threshold (direction=below) should NOT violate."""
    slo_orm = make_slo_orm(threshold_value=99.5, direction="below")

    slo_repo = MagicMock(spec=SLORepository)
    slo_repo.get_active_by_service_and_metric = AsyncMock(return_value=[slo_orm])

    svc = ServiceLevelObjectiveService(
        repo=slo_repo,
        service_repo=MagicMock(),
        spec_repo=MagicMock(),
    )
    EventBus.clear()
    await svc.check_violations("svc-id", "availability_pct", 99.9)

    assert slo_orm.state == "active"


@pytest.mark.asyncio
async def test_check_violations_no_threshold_skips_slo():
    """check_violations: SLO with no threshold_value should be skipped."""
    slo_orm = make_slo_orm(threshold_value=None, direction="above")

    slo_repo = MagicMock(spec=SLORepository)
    slo_repo.get_active_by_service_and_metric = AsyncMock(return_value=[slo_orm])

    svc = ServiceLevelObjectiveService(
        repo=slo_repo,
        service_repo=MagicMock(),
        spec_repo=MagicMock(),
    )
    EventBus.clear()
    await svc.check_violations("svc-id", "latency_ms", 999.0)

    assert slo_orm.state == "active"


# ── PerformanceMeasurementService ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_measurement_completed_triggers_check_violations():
    """patch_measurement to 'completed' should call slo_service.check_violations."""
    m_orm = make_measurement_orm(state="scheduled", metric_name="latency_ms")
    patched_orm = make_measurement_orm(state="completed", metric_name="latency_ms", metric_value=50.0)

    m_repo = MagicMock(spec=MeasurementRepository)
    m_repo.get_by_id = AsyncMock(return_value=m_orm)
    m_repo.patch = AsyncMock(return_value=patched_orm)

    slo_service = MagicMock(spec=ServiceLevelObjectiveService)
    slo_service.check_violations = AsyncMock()

    svc = PerformanceMeasurementService(
        repo=m_repo,
        service_repo=MagicMock(),
        slo_service=slo_service,
    )
    EventBus.clear()
    await svc.patch_measurement(
        "m-id", PerformanceMeasurementPatch(state="completed", metric_value=50.0)
    )

    slo_service.check_violations.assert_awaited_once_with("svc-id", "latency_ms", 50.0)


@pytest.mark.asyncio
async def test_patch_measurement_failed_does_not_trigger_check_violations():
    """patch_measurement to 'failed' should NOT call slo_service.check_violations."""
    m_orm = make_measurement_orm(state="scheduled")
    patched_orm = make_measurement_orm(state="failed")

    m_repo = MagicMock(spec=MeasurementRepository)
    m_repo.get_by_id = AsyncMock(return_value=m_orm)
    m_repo.patch = AsyncMock(return_value=patched_orm)

    slo_service = MagicMock(spec=ServiceLevelObjectiveService)
    slo_service.check_violations = AsyncMock()

    svc = PerformanceMeasurementService(
        repo=m_repo,
        service_repo=MagicMock(),
        slo_service=slo_service,
    )
    EventBus.clear()
    await svc.patch_measurement("m-id", PerformanceMeasurementPatch(state="failed"))

    slo_service.check_violations.assert_not_called()


@pytest.mark.asyncio
async def test_delete_measurement_scheduled_state_raises_422():
    """delete_measurement in 'scheduled' state should raise 422."""
    m_orm = make_measurement_orm(state="scheduled")
    m_repo = MagicMock(spec=MeasurementRepository)
    m_repo.get_by_id = AsyncMock(return_value=m_orm)

    svc = PerformanceMeasurementService(
        repo=m_repo, service_repo=MagicMock(), slo_service=MagicMock()
    )
    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_measurement("m-id")
    assert exc_info.value.status_code == 422
