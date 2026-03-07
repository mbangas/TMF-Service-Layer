"""Business logic for TMF653 Service Test Management.

Two service classes are co-located in this module:
  - ``TestSpecificationService`` — manages ServiceTestSpecification lifecycle
  - ``ServiceTestService``        — manages ServiceTest lifecycle + TestMeasure recording

ServiceTest lifecycle state machine:
    planned → inProgress | cancelled
    inProgress → completed | failed | cancelled

ServiceTestSpecification lifecycle state machine:
    active → retired → obsolete

TestMeasure records may only be added while the parent ServiceTest is ``inProgress``.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status

from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.inventory.repositories.service_repo import ServiceRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent
from src.testing.models.schemas import (
    DELETABLE_SPEC_STATES,
    DELETABLE_TEST_STATES,
    TEST_SPEC_TRANSITIONS,
    TEST_TRANSITIONS,
    VALID_TEST_MEASURE_RESULTS,
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


# ── TestSpecificationService ──────────────────────────────────────────────────

class TestSpecificationService:
    """Service layer for TMF653 ServiceTestSpecification.

    Manages lifecycle (active → retired → obsolete), optional catalog FK
    validation, and event publishing.
    """

    def __init__(
        self,
        repo: TestSpecificationRepository,
        catalog_repo: ServiceSpecificationRepository,
    ) -> None:
        self._repo = repo
        self._catalog_repo = catalog_repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_specs(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
    ) -> tuple[list[ServiceTestSpecificationResponse], int]:
        """Return a paginated list of test specifications.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(offset=offset, limit=limit, state=state)
        return [ServiceTestSpecificationResponse.model_validate(i) for i in items], total

    async def get_spec(self, spec_id: str) -> ServiceTestSpecificationResponse:
        """Retrieve a single test specification or raise 404.

        Args:
            spec_id: The specification UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(spec_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceTestSpecification '{spec_id}' not found.",
            )
        return ServiceTestSpecificationResponse.model_validate(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_spec(
        self, data: ServiceTestSpecificationCreate
    ) -> ServiceTestSpecificationResponse:
        """Create a new ServiceTestSpecification in ``active`` state.

        If ``service_spec_id`` is provided, validates it exists in the catalog.
        Publishes ``ServiceTestSpecificationCreateEvent``.

        Args:
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the catalog spec does not exist.
        """
        if data.service_spec_id is not None:
            catalog_spec = await self._catalog_repo.get_by_id(data.service_spec_id)
            if catalog_spec is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"ServiceSpecification '{data.service_spec_id}' not found. "
                        "The service_spec_id must reference an existing catalog specification."
                    ),
                )

        orm = await self._repo.create(data)
        response = ServiceTestSpecificationResponse.model_validate(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceTestSpecificationCreateEvent",
                domain="serviceTestManagement",
                title="Service Test Specification Created",
                description=f"ServiceTestSpecification '{orm.id}' created.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_spec(
        self, spec_id: str, data: ServiceTestSpecificationPatch
    ) -> ServiceTestSpecificationResponse:
        """Partial update of a ServiceTestSpecification with state machine enforcement.

        Publishes ``ServiceTestSpecificationStateChangeEvent`` on any state change.

        Args:
            spec_id: ID of the specification to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the state transition is invalid.
        """
        orm = await self._repo.get_by_id(spec_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceTestSpecification '{spec_id}' not found.",
            )

        state_changed = False
        if data.state is not None and data.state != orm.state:
            _validate_state_transition(orm.state, data.state, TEST_SPEC_TRANSITIONS, "ServiceTestSpecification")
            state_changed = True

        orm = await self._repo.patch(spec_id, data)
        response = ServiceTestSpecificationResponse.model_validate(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ServiceTestSpecificationStateChangeEvent",
                    domain="serviceTestManagement",
                    title="Service Test Specification State Changed",
                    description=f"ServiceTestSpecification '{spec_id}' transitioned to '{orm.state}'.",
                    event=EventPayload(resource=response),
                )
            )
        return response

    async def delete_spec(self, spec_id: str) -> None:
        """Delete a ServiceTestSpecification (only if in a deletable state).

        Args:
            spec_id: The specification UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if not in a deletable state.
        """
        orm = await self._repo.get_by_id(spec_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceTestSpecification '{spec_id}' not found.",
            )
        if orm.state not in DELETABLE_SPEC_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"ServiceTestSpecification '{spec_id}' cannot be deleted in state '{orm.state}'. "
                    f"Deletable states: {sorted(DELETABLE_SPEC_STATES)}"
                ),
            )
        await self._repo.delete(spec_id)


# ── ServiceTestService ────────────────────────────────────────────────────────

class ServiceTestService:
    """Service layer for TMF653 ServiceTest and TestMeasure.

    Manages test lifecycle, FK validation, state-driven timestamp assignment,
    and nested TestMeasure recording.  Publishes events on creation, state
    change, and completion/failure.
    """

    def __init__(
        self,
        repo: ServiceTestRepository,
        service_repo: ServiceRepository,
        spec_repo: TestSpecificationRepository,
    ) -> None:
        self._repo = repo
        self._service_repo = service_repo
        self._spec_repo = spec_repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_tests(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        service_id: str | None = None,
        test_spec_id: str | None = None,
    ) -> tuple[list[ServiceTestResponse], int]:
        """Return a paginated list of service tests with embedded measures.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.
            service_id: Optional service instance filter.
            test_spec_id: Optional test specification filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset, limit=limit, state=state,
            service_id=service_id, test_spec_id=test_spec_id,
        )
        responses = []
        for orm in items:
            measures = await self._repo.get_measures(orm.id)
            response = ServiceTestResponse.model_validate(orm)
            response.measures = [TestMeasureResponse.model_validate(m) for m in measures]
            responses.append(response)
        return responses, total

    async def get_test(self, test_id: str) -> ServiceTestResponse:
        """Retrieve a single service test with embedded measures, or raise 404.

        Args:
            test_id: The service test UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(test_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceTest '{test_id}' not found.",
            )
        measures = await self._repo.get_measures(test_id)
        response = ServiceTestResponse.model_validate(orm)
        response.measures = [TestMeasureResponse.model_validate(m) for m in measures]
        return response

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_test(self, data: ServiceTestCreate) -> ServiceTestResponse:
        """Create a new ServiceTest in ``planned`` state.

        Validates:
        - The target service exists and is in ``active`` state.
        - If ``test_spec_id`` is provided, the specification exists and is not ``obsolete``.

        Publishes ``ServiceTestCreateEvent``.

        Args:
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the service or spec does not exist.
            :class:`fastapi.HTTPException` (422) if the service is not active.
            :class:`fastapi.HTTPException` (422) if the spec is obsolete.
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
                    f"Service tests can only be created against services in 'active' state. "
                    f"Service '{data.service_id}' is currently in '{service.state}' state."
                ),
            )

        if data.test_spec_id is not None:
            spec = await self._spec_repo.get_by_id(data.test_spec_id)
            if spec is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ServiceTestSpecification '{data.test_spec_id}' not found.",
                )
            if spec.state == "obsolete":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"ServiceTestSpecification '{data.test_spec_id}' is 'obsolete' "
                        "and cannot be used for new tests."
                    ),
                )

        orm = await self._repo.create(data)
        response = ServiceTestResponse.model_validate(orm)
        response.measures = []

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceTestCreateEvent",
                domain="serviceTestManagement",
                title="Service Test Created",
                description=f"ServiceTest '{orm.id}' created for service '{data.service_id}'.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_test(
        self, test_id: str, data: ServiceTestPatch
    ) -> ServiceTestResponse:
        """Partial update of a ServiceTest with state machine enforcement.

        Sets ``start_date_time`` when transitioning to ``inProgress``.
        Sets ``end_date_time`` when transitioning to ``completed``, ``failed``,
        or ``cancelled``.
        Publishes ``ServiceTestCompleteEvent`` on ``completed``,
        ``ServiceTestFailedEvent`` on ``failed``,
        ``ServiceTestStateChangeEvent`` on other state changes.

        Args:
            test_id: ID of the test to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the state transition is invalid.
        """
        orm = await self._repo.get_by_id(test_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceTest '{test_id}' not found.",
            )

        state_changed = False
        new_state: str | None = None
        if data.state is not None and data.state != orm.state:
            _validate_state_transition(orm.state, data.state, TEST_TRANSITIONS, "ServiceTest")
            state_changed = True
            new_state = data.state
            now = datetime.now(tz=timezone.utc)
            if new_state == "inProgress":
                orm.start_date_time = now
            elif new_state in ("completed", "failed", "cancelled"):
                orm.end_date_time = now

        orm = await self._repo.patch(test_id, data)
        measures = await self._repo.get_measures(test_id)
        response = ServiceTestResponse.model_validate(orm)
        response.measures = [TestMeasureResponse.model_validate(m) for m in measures]

        if state_changed and new_state is not None:
            if new_state == "completed":
                event_type = "ServiceTestCompleteEvent"
                title = "Service Test Completed"
                description = f"ServiceTest '{test_id}' completed successfully."
            elif new_state == "failed":
                event_type = "ServiceTestFailedEvent"
                title = "Service Test Failed"
                description = f"ServiceTest '{test_id}' failed."
            else:
                event_type = "ServiceTestStateChangeEvent"
                title = "Service Test State Changed"
                description = f"ServiceTest '{test_id}' transitioned to '{new_state}'."

            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=event_type,
                    domain="serviceTestManagement",
                    title=title,
                    description=description,
                    event=EventPayload(resource=response),
                )
            )
        return response

    async def delete_test(self, test_id: str) -> None:
        """Delete a ServiceTest (only if in a terminal state).

        TestMeasure child records are removed automatically via CASCADE.

        Args:
            test_id: The service test UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if not in a deletable state.
        """
        orm = await self._repo.get_by_id(test_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceTest '{test_id}' not found.",
            )
        if orm.state not in DELETABLE_TEST_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"ServiceTest '{test_id}' cannot be deleted in state '{orm.state}'. "
                    f"Deletable states: {sorted(DELETABLE_TEST_STATES)}"
                ),
            )
        await self._repo.delete(test_id)

    # ── TestMeasure ───────────────────────────────────────────────────────────

    async def add_measure(
        self, test_id: str, data: TestMeasureCreate
    ) -> TestMeasureResponse:
        """Record a TestMeasure against an in-progress ServiceTest.

        Validates that the parent test exists and is in ``inProgress`` state.
        Validates ``result`` if provided.

        Args:
            test_id: The parent service test UUID.
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the test does not exist.
            :class:`fastapi.HTTPException` (422) if the test is not ``inProgress``.
            :class:`fastapi.HTTPException` (422) if the result value is invalid.
        """
        orm = await self._repo.get_by_id(test_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceTest '{test_id}' not found.",
            )
        if orm.state != "inProgress":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"TestMeasures can only be added to tests in 'inProgress' state. "
                    f"ServiceTest '{test_id}' is currently in '{orm.state}' state."
                ),
            )
        if data.result is not None and data.result not in VALID_TEST_MEASURE_RESULTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid result '{data.result}'. "
                    f"Valid values: {sorted(VALID_TEST_MEASURE_RESULTS)}"
                ),
            )

        measure = await self._repo.add_measure(test_id, data)
        return TestMeasureResponse.model_validate(measure)

    async def list_measures(self, test_id: str) -> list[TestMeasureResponse]:
        """Return all TestMeasures for a given service test.

        Args:
            test_id: Parent service test UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if the test does not exist.
        """
        orm = await self._repo.get_by_id(test_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceTest '{test_id}' not found.",
            )
        measures = await self._repo.get_measures(test_id)
        return [TestMeasureResponse.model_validate(m) for m in measures]
