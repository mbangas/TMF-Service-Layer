"""Business logic for TMF642 Alarm Management, TMF628 Performance Management,
and TMF657 Service Level Management.

All three service classes are co-located in this module to avoid a circular
import: ``PerformanceMeasurementService`` calls ``SLOService.check_violations``
after a measurement completes, and both classes need to be instantiated in the
same dependency factory.

Alarm lifecycle state machine:
    raised → acknowledged → cleared

Performance Measurement lifecycle state machine:
    scheduled → completed | failed

Service Level Objective lifecycle state machine:
    active ↔ violated  (violated only via check_violations, not PATCH)
    active | violated → suspended
    suspended → active
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status

from src.assurance.models.orm import AlarmOrm, PerformanceMeasurementOrm, ServiceLevelObjectiveOrm
from src.assurance.models.schemas import (
    ALARM_TRANSITIONS,
    DELETABLE_ALARM_STATES,
    DELETABLE_MEASUREMENT_STATES,
    DELETABLE_SLO_STATES,
    MEASUREMENT_TRANSITIONS,
    SLO_TRANSITIONS,
    VALID_ALARM_SEVERITIES,
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
from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.inventory.repositories.service_repo import ServiceRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent


# ── Shared helper ─────────────────────────────────────────────────────────────

def _validate_state_transition(
    current: str,
    requested: str,
    transitions: dict[str, set[str]],
    entity_name: str,
) -> None:
    """Raise HTTP 422 if the requested state transition is not permitted.

    Args:
        current: Current lifecycle state.
        requested: Requested target state.
        transitions: Allowed transition map for the entity type.
        entity_name: Human-readable entity name used in the error message.

    Raises:
        :class:`fastapi.HTTPException` (422) if the transition is invalid.
    """
    allowed = transitions.get(current, set())
    if requested not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid {entity_name} state transition from '{current}' to '{requested}'. "
                f"Allowed targets: {sorted(allowed) if allowed else 'none (terminal state)'}"
            ),
        )


# ── AlarmService ──────────────────────────────────────────────────────────────

class AlarmService:
    """Service layer for TMF642 Alarm Management.

    Applies business rules (active-service guard, state machine, timestamps,
    event publishing) on top of the raw CRUD from ``AlarmRepository``.
    """

    def __init__(
        self,
        repo: AlarmRepository,
        service_repo: ServiceRepository,
    ) -> None:
        self._repo = repo
        self._service_repo = service_repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_alarms(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        service_id: str | None = None,
    ) -> tuple[list[AlarmResponse], int]:
        """Return a paginated list of alarms.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.
            service_id: Optional service instance filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset, limit=limit, state=state, service_id=service_id
        )
        return [AlarmResponse.model_validate(i) for i in items], total

    async def get_alarm(self, alarm_id: str) -> AlarmResponse:
        """Retrieve a single alarm or raise 404.

        Args:
            alarm_id: The alarm UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(alarm_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alarm '{alarm_id}' not found.",
            )
        return AlarmResponse.model_validate(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_alarm(self, data: AlarmCreate) -> AlarmResponse:
        """Create a new Alarm against an active Service instance.

        Validates that the target service exists and is in ``active`` state.
        Validates severity if provided.  Publishes ``AlarmCreateEvent``.

        Args:
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the service does not exist.
            :class:`fastapi.HTTPException` (422) if the service is not active.
            :class:`fastapi.HTTPException` (422) if the severity is invalid.
        """
        service = await self._service_repo.get_by_id(data.service_id)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{data.service_id}' not found.",
            )
        if service.state != "active":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Alarms can only be raised against services in 'active' state. "
                    f"Service '{data.service_id}' is currently in '{service.state}' state."
                ),
            )
        if data.severity is not None and data.severity not in VALID_ALARM_SEVERITIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid severity '{data.severity}'. "
                    f"Valid values: {sorted(VALID_ALARM_SEVERITIES)}"
                ),
            )

        orm = await self._repo.create(data)
        response = AlarmResponse.model_validate(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="AlarmCreateEvent",
                domain="alarmManagement",
                title="Alarm Created",
                description=f"Alarm '{orm.id}' raised for service '{data.service_id}'.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_alarm(self, alarm_id: str, data: AlarmPatch) -> AlarmResponse:
        """Partial update of an Alarm with state machine enforcement.

        Sets ``acknowledged_at`` when transitioning to ``acknowledged``,
        ``cleared_at`` when transitioning to ``cleared``.
        Publishes ``AlarmStateChangeEvent`` on any state change.

        Args:
            alarm_id: ID of the alarm to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the state transition is invalid.
        """
        orm = await self._repo.get_by_id(alarm_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alarm '{alarm_id}' not found.",
            )

        state_changed = False
        if data.state is not None and data.state != orm.state:
            _validate_state_transition(orm.state, data.state, ALARM_TRANSITIONS, "alarm")
            state_changed = True
            now = datetime.now(tz=timezone.utc)
            if data.state == "acknowledged":
                data = data.model_copy(update={"state": data.state})
                orm.acknowledged_at = now
            elif data.state == "cleared":
                orm.cleared_at = now

        orm = await self._repo.patch(alarm_id, data)
        response = AlarmResponse.model_validate(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="AlarmStateChangeEvent",
                    domain="alarmManagement",
                    title="Alarm State Changed",
                    description=f"Alarm '{alarm_id}' transitioned to '{orm.state}'.",
                    event=EventPayload(resource=response),
                )
            )
        return response

    async def delete_alarm(self, alarm_id: str) -> None:
        """Delete an Alarm (only if in a deletable state).

        Args:
            alarm_id: The alarm UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if not in a deletable state.
        """
        orm = await self._repo.get_by_id(alarm_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alarm '{alarm_id}' not found.",
            )
        if orm.state not in DELETABLE_ALARM_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Alarm '{alarm_id}' cannot be deleted in state '{orm.state}'. "
                    f"Deletable states: {sorted(DELETABLE_ALARM_STATES)}"
                ),
            )
        await self._repo.delete(alarm_id)


# ── ServiceLevelObjectiveService ──────────────────────────────────────────────

class ServiceLevelObjectiveService:
    """Service layer for TMF657 Service Level Management.

    Manages SLO lifecycle, FK validation, and violation detection via
    ``check_violations``.  Referenced by ``PerformanceMeasurementService``
    after a measurement completes.
    """

    def __init__(
        self,
        repo: SLORepository,
        service_repo: ServiceRepository,
        spec_repo: ServiceSpecificationRepository,
    ) -> None:
        self._repo = repo
        self._service_repo = service_repo
        self._spec_repo = spec_repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_slos(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        service_id: str | None = None,
    ) -> tuple[list[ServiceLevelObjectiveResponse], int]:
        """Return a paginated list of SLOs.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.
            service_id: Optional service instance filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset, limit=limit, state=state, service_id=service_id
        )
        return [ServiceLevelObjectiveResponse.model_validate(i) for i in items], total

    async def get_slo(self, slo_id: str) -> ServiceLevelObjectiveResponse:
        """Retrieve a single SLO or raise 404.

        Args:
            slo_id: The SLO UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(slo_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceLevelObjective '{slo_id}' not found.",
            )
        return ServiceLevelObjectiveResponse.model_validate(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_slo(self, data: ServiceLevelObjectiveCreate) -> ServiceLevelObjectiveResponse:
        """Create a new ServiceLevelObjective.

        Validates that the target service exists.  If ``sls_id`` is provided,
        validates that the SLS exists in the catalog.
        Publishes ``ServiceLevelObjectiveCreateEvent``.

        Args:
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the service or SLS does not exist.
        """
        service = await self._service_repo.get_by_id(data.service_id)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{data.service_id}' not found.",
            )

        if data.sls_id is not None:
            sls = await self._spec_repo.get_sls_by_id(data.sls_id)
            if sls is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"ServiceLevelSpecification '{data.sls_id}' not found. "
                        "The sls_id must reference an existing catalog SLS."
                    ),
                )

        orm = await self._repo.create(data)
        response = ServiceLevelObjectiveResponse.model_validate(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceLevelObjectiveCreateEvent",
                domain="serviceLevelManagement",
                title="Service Level Objective Created",
                description=f"SLO '{orm.id}' created for service '{data.service_id}'.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_slo(
        self, slo_id: str, data: ServiceLevelObjectivePatch
    ) -> ServiceLevelObjectiveResponse:
        """Partial update of a ServiceLevelObjective.

        Validates state transitions.  Publishes ``ServiceLevelObjectiveStateChangeEvent``
        on any state change.

        Args:
            slo_id: ID of the SLO to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the state transition is invalid.
        """
        orm = await self._repo.get_by_id(slo_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceLevelObjective '{slo_id}' not found.",
            )

        state_changed = False
        if data.state is not None and data.state != orm.state:
            _validate_state_transition(orm.state, data.state, SLO_TRANSITIONS, "SLO")
            state_changed = True

        orm = await self._repo.patch(slo_id, data)
        response = ServiceLevelObjectiveResponse.model_validate(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ServiceLevelObjectiveStateChangeEvent",
                    domain="serviceLevelManagement",
                    title="Service Level Objective State Changed",
                    description=f"SLO '{slo_id}' transitioned to '{orm.state}'.",
                    event=EventPayload(resource=response),
                )
            )
        return response

    async def delete_slo(self, slo_id: str) -> None:
        """Delete a ServiceLevelObjective (only if in a deletable state).

        Args:
            slo_id: The SLO UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if not in a deletable state.
        """
        orm = await self._repo.get_by_id(slo_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceLevelObjective '{slo_id}' not found.",
            )
        if orm.state not in DELETABLE_SLO_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"ServiceLevelObjective '{slo_id}' cannot be deleted in state '{orm.state}'. "
                    f"Deletable states: {sorted(DELETABLE_SLO_STATES)}"
                ),
            )
        await self._repo.delete(slo_id)

    async def check_violations(
        self, service_id: str, metric_name: str, metric_value: float
    ) -> tuple[list[ServiceLevelObjectiveResponse], list[ServiceLevelObjectiveResponse]]:
        """Evaluate active SLOs for threshold breaches and flip them to ``violated``.

        Called automatically by ``PerformanceMeasurementService.patch_measurement``
        whenever a measurement transitions to ``completed``, and also exposed
        directly via ``POST /serviceLevel/check_violations``.

        For each active SLO matching ``service_id`` and ``metric_name``:
        - ``direction == 'above'`` → violated if ``metric_value > threshold_value``
        - ``direction == 'below'`` → violated if ``metric_value < threshold_value``

        Publishes a ``ServiceLevelObjectiveViolationEvent`` for each violation detected.

        Args:
            service_id: The service instance UUID from the completed measurement.
            metric_name: The metric identifier from the completed measurement.
            metric_value: The measured value to evaluate against thresholds.

        Returns:
            Tuple of (all_evaluated_responses, newly_violated_responses).
        """
        active_slos = await self._repo.get_active_by_service_and_metric(service_id, metric_name)

        all_responses: list[ServiceLevelObjectiveResponse] = []
        violated_responses: list[ServiceLevelObjectiveResponse] = []

        for slo in active_slos:
            if slo.threshold_value is None or slo.direction is None:
                all_responses.append(ServiceLevelObjectiveResponse.model_validate(slo))
                continue

            breached = (
                (slo.direction == "above" and metric_value > slo.threshold_value)
                or (slo.direction == "below" and metric_value < slo.threshold_value)
            )

            if breached:
                slo.state = "violated"
                await self._repo._db.flush()
                await self._repo._db.refresh(slo)
                response = ServiceLevelObjectiveResponse.model_validate(slo)

                EventBus.publish(
                    TMFEvent(
                        event_id=str(uuid.uuid4()),
                        event_type="ServiceLevelObjectiveViolationEvent",
                        domain="serviceLevelManagement",
                        title="Service Level Objective Violated",
                        description=(
                            f"SLO '{slo.id}' violated: "
                            f"metric '{metric_name}' = {metric_value} "
                            f"(threshold {slo.direction} {slo.threshold_value})."
                        ),
                        event=EventPayload(resource=response),
                    )
                )
                violated_responses.append(response)
            else:
                all_responses.append(ServiceLevelObjectiveResponse.model_validate(slo))

        return all_responses + violated_responses, violated_responses


# ── PerformanceMeasurementService ─────────────────────────────────────────────

class PerformanceMeasurementService:
    """Service layer for TMF628 Performance Management.

    After a measurement transitions to ``completed``, automatically triggers
    SLO violation detection via ``ServiceLevelObjectiveService.check_violations``.
    """

    def __init__(
        self,
        repo: MeasurementRepository,
        service_repo: ServiceRepository,
        slo_service: ServiceLevelObjectiveService,
    ) -> None:
        self._repo = repo
        self._service_repo = service_repo
        self._slo_service = slo_service

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_measurements(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        service_id: str | None = None,
    ) -> tuple[list[PerformanceMeasurementResponse], int]:
        """Return a paginated list of measurements.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.
            service_id: Optional service instance filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset, limit=limit, state=state, service_id=service_id
        )
        return [PerformanceMeasurementResponse.model_validate(i) for i in items], total

    async def get_measurement(self, measurement_id: str) -> PerformanceMeasurementResponse:
        """Retrieve a single measurement or raise 404.

        Args:
            measurement_id: The measurement UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(measurement_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PerformanceMeasurement '{measurement_id}' not found.",
            )
        return PerformanceMeasurementResponse.model_validate(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_measurement(
        self, data: PerformanceMeasurementCreate
    ) -> PerformanceMeasurementResponse:
        """Create a new PerformanceMeasurement in ``scheduled`` state.

        Validates that the target service exists.
        Publishes ``PerformanceMeasurementCreateEvent``.

        Args:
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the service does not exist.
        """
        service = await self._service_repo.get_by_id(data.service_id)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{data.service_id}' not found.",
            )

        orm = await self._repo.create(data)
        response = PerformanceMeasurementResponse.model_validate(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="PerformanceMeasurementCreateEvent",
                domain="performanceManagement",
                title="Performance Measurement Created",
                description=f"Measurement '{orm.id}' scheduled for service '{data.service_id}'.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_measurement(
        self, measurement_id: str, data: PerformanceMeasurementPatch
    ) -> PerformanceMeasurementResponse:
        """Partial update of a PerformanceMeasurement with state machine enforcement.

        When transitioning to ``completed``, automatically triggers SLO violation
        detection for the same service and metric combination.

        Args:
            measurement_id: ID of the measurement to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the state transition is invalid.
        """
        orm = await self._repo.get_by_id(measurement_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PerformanceMeasurement '{measurement_id}' not found.",
            )

        state_changed = False
        transitioning_to_completed = False
        if data.state is not None and data.state != orm.state:
            _validate_state_transition(
                orm.state, data.state, MEASUREMENT_TRANSITIONS, "measurement"
            )
            state_changed = True
            if data.state == "completed":
                transitioning_to_completed = True
                if data.completed_at is None:
                    orm.completed_at = datetime.now(tz=timezone.utc)

        # Capture service_id and metric details before the patch for violation check
        service_id = orm.service_id
        metric_name = orm.metric_name
        # Use patch metric_value if provided, otherwise fall back to existing value
        metric_value = data.metric_value if data.metric_value is not None else orm.metric_value

        orm = await self._repo.patch(measurement_id, data)
        response = PerformanceMeasurementResponse.model_validate(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="PerformanceMeasurementStateChangeEvent",
                    domain="performanceManagement",
                    title="Performance Measurement State Changed",
                    description=f"Measurement '{measurement_id}' transitioned to '{orm.state}'.",
                    event=EventPayload(resource=response),
                )
            )

        # Trigger SLO violation check only when completing with a metric value
        if transitioning_to_completed and metric_value is not None:
            await self._slo_service.check_violations(service_id, metric_name, metric_value)

        return response

    async def delete_measurement(self, measurement_id: str) -> None:
        """Delete a PerformanceMeasurement (only if in a deletable state).

        Args:
            measurement_id: The measurement UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if not in a deletable state.
        """
        orm = await self._repo.get_by_id(measurement_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PerformanceMeasurement '{measurement_id}' not found.",
            )
        if orm.state not in DELETABLE_MEASUREMENT_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"PerformanceMeasurement '{measurement_id}' cannot be deleted in state "
                    f"'{orm.state}'. Deletable states: {sorted(DELETABLE_MEASUREMENT_STATES)}"
                ),
            )
        await self._repo.delete(measurement_id)
