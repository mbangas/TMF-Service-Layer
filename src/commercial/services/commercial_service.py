"""Business logic for TMF648 Quote Management and TMF651 Agreement Management.

Quote lifecycle state machine:
    inProgress → pending | cancelled
    pending → approved | rejected | inProgress
    approved → accepted | cancelled
    Terminal: accepted | rejected | cancelled

Agreement lifecycle state machine:
    inProgress → active | cancelled
    active → expired | terminated
    Terminal: expired | terminated | cancelled
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status

from src.commercial.models.orm import AgreementOrm, QuoteOrm
from src.commercial.models.schemas import (
    AGREEMENT_TRANSITIONS,
    QUOTE_TRANSITIONS,
    VALID_AGREEMENT_STATUS_CHANGE_STATES,
    VALID_AGREEMENT_TYPES,
    VALID_CONFORMANCE_PERIODS,
    VALID_METRICS,
    VALID_METRIC_UNITS,
    VALID_PRICE_TYPES,
    VALID_QUOTE_COMPLETION_STATES,
    AgreementCreate,
    AgreementPatch,
    AgreementResponse,
    QuoteCreate,
    QuoteItemCreate,
    QuoteItemResponse,
    QuotePatch,
    QuoteResponse,
    ServiceLevelAgreementCreate,
    ServiceLevelAgreementResponse,
)
from src.commercial.repositories.agreement_repo import AgreementRepository
from src.commercial.repositories.quote_repo import QuoteRepository
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
        entity_name: Human-readable entity name for the error message.

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


# ── QuoteService ──────────────────────────────────────────────────────────────

class QuoteService:
    """Service layer for TMF648 Quote Management.

    Validates FK references (service spec), enforces state machine transitions,
    auto-sets ``completion_date`` on accepted/rejected, and publishes TMF events.
    """

    def __init__(
        self,
        repo: QuoteRepository,
        spec_repo,  # src.catalog.repositories.service_spec_repo.ServiceSpecificationRepository
    ) -> None:
        self._repo = repo
        self._spec_repo = spec_repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_quotes(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        category: str | None = None,
        related_service_spec_id: str | None = None,
    ) -> tuple[list[QuoteResponse], int]:
        """Return a paginated list of quotes.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.
            category: Optional category filter.
            related_service_spec_id: Optional service spec filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset, limit=limit,
            state=state, category=category,
            related_service_spec_id=related_service_spec_id,
        )
        return [QuoteResponse.model_validate(i) for i in items], total

    async def get_quote(self, quote_id: str) -> QuoteResponse:
        """Retrieve a single quote or raise 404.

        Args:
            quote_id: The quote UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(quote_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quote '{quote_id}' not found.",
            )
        return QuoteResponse.model_validate(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_quote(self, data: QuoteCreate) -> QuoteResponse:
        """Create a new Quote in ``inProgress`` state.

        Validates that ``related_service_spec_id`` exists if provided.

        Args:
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the service spec FK does not exist.
            :class:`fastapi.HTTPException` (422) if item action or price_type values are invalid.
        """
        if data.related_service_spec_id is not None:
            spec = await self._spec_repo.get_by_id(data.related_service_spec_id)
            if spec is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ServiceSpecification '{data.related_service_spec_id}' not found.",
                )

        orm = await self._repo.create(data)
        response = QuoteResponse.model_validate(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="QuoteCreateEvent",
                domain="quoteManagement",
                title="Quote Created",
                description=f"Quote '{orm.id}' created.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_quote(self, quote_id: str, data: QuotePatch) -> QuoteResponse:
        """Partial update of a Quote with state machine enforcement.

        Auto-sets ``completion_date`` when transitioning to ``accepted`` or ``rejected``.

        Args:
            quote_id: ID of the quote to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the state transition is invalid.
        """
        orm = await self._repo.get_by_id(quote_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quote '{quote_id}' not found.",
            )

        state_changed = False
        if data.state is not None and data.state != orm.state:
            _validate_state_transition(orm.state, data.state, QUOTE_TRANSITIONS, "quote")
            state_changed = True
            if data.state in VALID_QUOTE_COMPLETION_STATES:
                orm.completion_date = datetime.now(tz=timezone.utc)

        orm = await self._repo.patch(quote_id, data)
        response = QuoteResponse.model_validate(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="QuoteStateChangeEvent",
                    domain="quoteManagement",
                    title="Quote State Changed",
                    description=f"Quote '{quote_id}' transitioned to '{orm.state}'.",
                    event=EventPayload(resource=response),
                )
            )
        return response

    async def delete_quote(self, quote_id: str) -> None:
        """Delete a Quote.

        Args:
            quote_id: The quote UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(quote_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quote '{quote_id}' not found.",
            )
        await self._repo.delete(quote_id)

    # ── Items ─────────────────────────────────────────────────────────────────

    async def add_item(self, quote_id: str, data: QuoteItemCreate) -> QuoteItemResponse:
        """Append a QuoteItem to a Quote.

        Args:
            quote_id: Parent quote UUID.
            data: Item create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the quote does not exist.
        """
        orm = await self._repo.get_by_id(quote_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quote '{quote_id}' not found.",
            )
        item = await self._repo.add_item(quote_id, data)
        return QuoteItemResponse.model_validate(item)

    async def delete_item(self, quote_id: str, item_id: str) -> None:
        """Delete a QuoteItem from a Quote.

        Args:
            quote_id: Parent quote UUID (used for 404 guard on the parent).
            item_id: Item UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if the quote or item is not found.
        """
        orm = await self._repo.get_by_id(quote_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quote '{quote_id}' not found.",
            )
        deleted = await self._repo.delete_item(item_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"QuoteItem '{item_id}' not found on Quote '{quote_id}'.",
            )


# ── AgreementService ──────────────────────────────────────────────────────────

class AgreementService:
    """Service layer for TMF651 Agreement Management.

    Validates FK references (spec, quote, service), enforces state machine transitions,
    auto-sets ``status_change_date`` on state change, and publishes TMF events.
    """

    def __init__(
        self,
        repo: AgreementRepository,
        spec_repo,    # src.catalog.repositories.service_spec_repo.ServiceSpecificationRepository
        quote_repo: QuoteRepository,
        service_repo, # src.inventory.repositories.service_repo.ServiceRepository
    ) -> None:
        self._repo = repo
        self._spec_repo = spec_repo
        self._quote_repo = quote_repo
        self._service_repo = service_repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_agreements(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        agreement_type: str | None = None,
        related_service_spec_id: str | None = None,
    ) -> tuple[list[AgreementResponse], int]:
        """Return a paginated list of agreements.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.
            agreement_type: Optional type filter.
            related_service_spec_id: Optional service spec filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset, limit=limit,
            state=state, agreement_type=agreement_type,
            related_service_spec_id=related_service_spec_id,
        )
        return [AgreementResponse.model_validate(i) for i in items], total

    async def get_agreement(self, agreement_id: str) -> AgreementResponse:
        """Retrieve a single agreement or raise 404.

        Args:
            agreement_id: The agreement UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(agreement_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agreement '{agreement_id}' not found.",
            )
        return AgreementResponse.model_validate(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_agreement(self, data: AgreementCreate) -> AgreementResponse:
        """Create a new Agreement in ``inProgress`` state.

        Validates FK references for service spec, quote, and service if provided.

        Args:
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if any FK reference does not exist.
        """
        if data.related_service_spec_id is not None:
            spec = await self._spec_repo.get_by_id(data.related_service_spec_id)
            if spec is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ServiceSpecification '{data.related_service_spec_id}' not found.",
                )

        if data.related_quote_id is not None:
            quote = await self._quote_repo.get_by_id(data.related_quote_id)
            if quote is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Quote '{data.related_quote_id}' not found.",
                )

        if data.related_service_id is not None:
            svc = await self._service_repo.get_by_id(data.related_service_id)
            if svc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Service '{data.related_service_id}' not found.",
                )

        orm = await self._repo.create(data)
        response = AgreementResponse.model_validate(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="AgreementCreateEvent",
                domain="agreementManagement",
                title="Agreement Created",
                description=f"Agreement '{orm.id}' created.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_agreement(self, agreement_id: str, data: AgreementPatch) -> AgreementResponse:
        """Partial update of an Agreement with state machine enforcement.

        Auto-sets ``status_change_date`` on any state change.

        Args:
            agreement_id: ID of the agreement to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the state transition is invalid.
        """
        orm = await self._repo.get_by_id(agreement_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agreement '{agreement_id}' not found.",
            )

        state_changed = False
        if data.state is not None and data.state != orm.state:
            _validate_state_transition(orm.state, data.state, AGREEMENT_TRANSITIONS, "agreement")
            state_changed = True
            orm.status_change_date = datetime.now(tz=timezone.utc)

        orm = await self._repo.patch(agreement_id, data)
        response = AgreementResponse.model_validate(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="AgreementStateChangeEvent",
                    domain="agreementManagement",
                    title="Agreement State Changed",
                    description=f"Agreement '{agreement_id}' transitioned to '{orm.state}'.",
                    event=EventPayload(resource=response),
                )
            )
        return response

    async def delete_agreement(self, agreement_id: str) -> None:
        """Delete an Agreement.

        Args:
            agreement_id: The agreement UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(agreement_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agreement '{agreement_id}' not found.",
            )
        await self._repo.delete(agreement_id)

    # ── SLAs ──────────────────────────────────────────────────────────────────

    async def add_sla(
        self, agreement_id: str, data: ServiceLevelAgreementCreate
    ) -> ServiceLevelAgreementResponse:
        """Append an SLA metric to an Agreement.

        Args:
            agreement_id: Parent agreement UUID.
            data: SLA create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the agreement does not exist.
        """
        orm = await self._repo.get_by_id(agreement_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agreement '{agreement_id}' not found.",
            )
        sla = await self._repo.add_sla(agreement_id, data)
        return ServiceLevelAgreementResponse.model_validate(sla)

    async def delete_sla(self, agreement_id: str, sla_id: str) -> None:
        """Delete an SLA from an Agreement.

        Args:
            agreement_id: Parent agreement UUID (used for 404 guard on the parent).
            sla_id: SLA UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if the agreement or SLA is not found.
        """
        orm = await self._repo.get_by_id(agreement_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agreement '{agreement_id}' not found.",
            )
        deleted = await self._repo.delete_sla(sla_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceLevelAgreement '{sla_id}' not found on Agreement '{agreement_id}'.",
            )
