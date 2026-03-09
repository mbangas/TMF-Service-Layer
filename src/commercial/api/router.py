"""Commercial management REST API router — TMF648 and TMF651.

Two sub-routers are aggregated into a single ``router`` exported from this module:

    TMF648 - Quote Management
        GET    /tmf-api/quoteManagement/v4/quote
        POST   /tmf-api/quoteManagement/v4/quote
        GET    /tmf-api/quoteManagement/v4/quote/{quote_id}
        PATCH  /tmf-api/quoteManagement/v4/quote/{quote_id}
        DELETE /tmf-api/quoteManagement/v4/quote/{quote_id}

        GET    /tmf-api/quoteManagement/v4/quote/{quote_id}/quoteItem
        POST   /tmf-api/quoteManagement/v4/quote/{quote_id}/quoteItem
        DELETE /tmf-api/quoteManagement/v4/quote/{quote_id}/quoteItem/{item_id}

    TMF651 - Agreement Management
        GET    /tmf-api/agreementManagement/v4/agreement
        POST   /tmf-api/agreementManagement/v4/agreement
        GET    /tmf-api/agreementManagement/v4/agreement/{agreement_id}
        PATCH  /tmf-api/agreementManagement/v4/agreement/{agreement_id}
        DELETE /tmf-api/agreementManagement/v4/agreement/{agreement_id}

        GET    /tmf-api/agreementManagement/v4/agreement/{agreement_id}/agreementItem
        POST   /tmf-api/agreementManagement/v4/agreement/{agreement_id}/agreementItem
        DELETE /tmf-api/agreementManagement/v4/agreement/{agreement_id}/agreementItem/{sla_id}
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.commercial.models.schemas import (
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
from src.commercial.services.commercial_service import AgreementService, QuoteService
from src.inventory.repositories.service_repo import ServiceRepository
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

# ── Dependency factories ───────────────────────────────────────────────────────


def _get_quote_service(db: AsyncSession = Depends(get_db)) -> QuoteService:
    """Dependency factory — builds QuoteService with its dependencies."""
    return QuoteService(
        repo=QuoteRepository(db),
        spec_repo=ServiceSpecificationRepository(db),
    )


def _get_agreement_service(db: AsyncSession = Depends(get_db)) -> AgreementService:
    """Dependency factory — builds AgreementService with its dependencies."""
    return AgreementService(
        repo=AgreementRepository(db),
        spec_repo=ServiceSpecificationRepository(db),
        quote_repo=QuoteRepository(db),
        service_repo=ServiceRepository(db),
    )


# ── TMF648 - Quote Management ─────────────────────────────────────────────────

quote_router = APIRouter(
    prefix="/tmf-api/quoteManagement/v4/quote",
    tags=["TMF648 - Quote Management"],
)


@quote_router.get(
    "",
    response_model=list[QuoteResponse],
    summary="List Quotes",
    status_code=status.HTTP_200_OK,
)
async def list_quotes(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by quote state"),
    category: str | None = Query(default=None, description="Filter by category"),
    related_service_spec_id: str | None = Query(
        default=None, description="Filter by ServiceSpecification UUID"
    ),
    svc: QuoteService = Depends(_get_quote_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[QuoteResponse]:
    """Retrieve a paginated list of ``Quote`` instances (TMF648 §6.1.1)."""
    items, total = await svc.list_quotes(
        offset=offset, limit=limit, state=state,
        category=category, related_service_spec_id=related_service_spec_id,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@quote_router.post(
    "",
    response_model=QuoteResponse,
    summary="Create a Quote",
    status_code=status.HTTP_201_CREATED,
)
async def create_quote(
    data: QuoteCreate,
    svc: QuoteService = Depends(_get_quote_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> QuoteResponse:
    """Create a new ``Quote`` in ``inProgress`` state (TMF648 §6.1.1)."""
    return await svc.create_quote(data)


@quote_router.get(
    "/{quote_id}",
    response_model=QuoteResponse,
    summary="Retrieve a Quote",
    status_code=status.HTTP_200_OK,
)
async def get_quote(
    quote_id: str,
    svc: QuoteService = Depends(_get_quote_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> QuoteResponse:
    """Retrieve a single ``Quote`` by its ID (TMF648 §6.1.2)."""
    return await svc.get_quote(quote_id)


@quote_router.patch(
    "/{quote_id}",
    response_model=QuoteResponse,
    summary="Update a Quote",
    status_code=status.HTTP_200_OK,
)
async def patch_quote(
    quote_id: str,
    data: QuotePatch,
    svc: QuoteService = Depends(_get_quote_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> QuoteResponse:
    """Partial update / state transition of a ``Quote`` (TMF648 §6.1.2)."""
    return await svc.patch_quote(quote_id, data)


@quote_router.delete(
    "/{quote_id}",
    response_class=Response,
    summary="Delete a Quote",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_quote(
    quote_id: str,
    svc: QuoteService = Depends(_get_quote_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``Quote`` (TMF648 §6.1.2)."""
    await svc.delete_quote(quote_id)


# ── TMF648 - QuoteItem sub-resource ──────────────────────────────────────────

quote_item_router = APIRouter(
    prefix="/tmf-api/quoteManagement/v4/quote/{quote_id}/quoteItem",
    tags=["TMF648 - Quote Management"],
)


@quote_item_router.get(
    "",
    response_model=list[QuoteItemResponse],
    summary="List QuoteItems on a Quote",
    status_code=status.HTTP_200_OK,
)
async def list_quote_items(
    quote_id: str,
    svc: QuoteService = Depends(_get_quote_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[QuoteItemResponse]:
    """Retrieve all items attached to a ``Quote``."""
    quote = await svc.get_quote(quote_id)
    return quote.items


@quote_item_router.post(
    "",
    response_model=QuoteItemResponse,
    summary="Add a QuoteItem to a Quote",
    status_code=status.HTTP_201_CREATED,
)
async def add_quote_item(
    quote_id: str,
    data: QuoteItemCreate,
    svc: QuoteService = Depends(_get_quote_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> QuoteItemResponse:
    """Append a new item to a ``Quote``."""
    return await svc.add_item(quote_id, data)


@quote_item_router.delete(
    "/{item_id}",
    response_class=Response,
    summary="Delete a QuoteItem from a Quote",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_quote_item(
    quote_id: str,
    item_id: str,
    svc: QuoteService = Depends(_get_quote_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a single item from a ``Quote``."""
    await svc.delete_item(quote_id, item_id)


# ── TMF651 - Agreement Management ─────────────────────────────────────────────

agreement_router = APIRouter(
    prefix="/tmf-api/agreementManagement/v4/agreement",
    tags=["TMF651 - Agreement Management"],
)


@agreement_router.get(
    "",
    response_model=list[AgreementResponse],
    summary="List Agreements",
    status_code=status.HTTP_200_OK,
)
async def list_agreements(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by agreement state"),
    agreement_type: str | None = Query(default=None, description="Filter by agreement type"),
    related_service_spec_id: str | None = Query(
        default=None, description="Filter by ServiceSpecification UUID"
    ),
    svc: AgreementService = Depends(_get_agreement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[AgreementResponse]:
    """Retrieve a paginated list of ``Agreement`` instances (TMF651 §6.1.1)."""
    items, total = await svc.list_agreements(
        offset=offset, limit=limit, state=state,
        agreement_type=agreement_type, related_service_spec_id=related_service_spec_id,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@agreement_router.post(
    "",
    response_model=AgreementResponse,
    summary="Create an Agreement",
    status_code=status.HTTP_201_CREATED,
)
async def create_agreement(
    data: AgreementCreate,
    svc: AgreementService = Depends(_get_agreement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> AgreementResponse:
    """Create a new ``Agreement`` in ``inProgress`` state (TMF651 §6.1.1)."""
    return await svc.create_agreement(data)


@agreement_router.get(
    "/{agreement_id}",
    response_model=AgreementResponse,
    summary="Retrieve an Agreement",
    status_code=status.HTTP_200_OK,
)
async def get_agreement(
    agreement_id: str,
    svc: AgreementService = Depends(_get_agreement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> AgreementResponse:
    """Retrieve a single ``Agreement`` by its ID (TMF651 §6.1.2)."""
    return await svc.get_agreement(agreement_id)


@agreement_router.patch(
    "/{agreement_id}",
    response_model=AgreementResponse,
    summary="Update an Agreement",
    status_code=status.HTTP_200_OK,
)
async def patch_agreement(
    agreement_id: str,
    data: AgreementPatch,
    svc: AgreementService = Depends(_get_agreement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> AgreementResponse:
    """Partial update / state transition of an ``Agreement`` (TMF651 §6.1.2)."""
    return await svc.patch_agreement(agreement_id, data)


@agreement_router.delete(
    "/{agreement_id}",
    response_class=Response,
    summary="Delete an Agreement",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_agreement(
    agreement_id: str,
    svc: AgreementService = Depends(_get_agreement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete an ``Agreement`` (TMF651 §6.1.2)."""
    await svc.delete_agreement(agreement_id)


# ── TMF651 - SLA sub-resource ─────────────────────────────────────────────────

agreement_item_router = APIRouter(
    prefix="/tmf-api/agreementManagement/v4/agreement/{agreement_id}/agreementItem",
    tags=["TMF651 - Agreement Management"],
)


@agreement_item_router.get(
    "",
    response_model=list[ServiceLevelAgreementResponse],
    summary="List SLA metrics on an Agreement",
    status_code=status.HTTP_200_OK,
)
async def list_agreement_slas(
    agreement_id: str,
    svc: AgreementService = Depends(_get_agreement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceLevelAgreementResponse]:
    """Retrieve all SLA metrics attached to an ``Agreement``."""
    agreement = await svc.get_agreement(agreement_id)
    return agreement.slas


@agreement_item_router.post(
    "",
    response_model=ServiceLevelAgreementResponse,
    summary="Add an SLA metric to an Agreement",
    status_code=status.HTTP_201_CREATED,
)
async def add_agreement_sla(
    agreement_id: str,
    data: ServiceLevelAgreementCreate,
    svc: AgreementService = Depends(_get_agreement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceLevelAgreementResponse:
    """Append a new SLA metric to an ``Agreement``."""
    return await svc.add_sla(agreement_id, data)


@agreement_item_router.delete(
    "/{sla_id}",
    response_class=Response,
    summary="Delete an SLA metric from an Agreement",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_agreement_sla(
    agreement_id: str,
    sla_id: str,
    svc: AgreementService = Depends(_get_agreement_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a single SLA metric from an ``Agreement``."""
    await svc.delete_sla(agreement_id, sla_id)


# ── Aggregated router ─────────────────────────────────────────────────────────

router = APIRouter()
router.include_router(quote_router)
router.include_router(quote_item_router)
router.include_router(agreement_router)
router.include_router(agreement_item_router)
