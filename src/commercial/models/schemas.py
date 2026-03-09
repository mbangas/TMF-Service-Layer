"""Pydantic schemas for TMF648 Quote Management and TMF651 Agreement Management."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity

# ── State machine constants ────────────────────────────────────────────────────

QUOTE_TRANSITIONS: dict[str, set[str]] = {
    "inProgress": {"pending", "cancelled"},
    "pending": {"approved", "rejected", "inProgress"},
    "approved": {"accepted", "cancelled"},
    "accepted": set(),   # terminal
    "rejected": set(),   # terminal
    "cancelled": set(),  # terminal
}

AGREEMENT_TRANSITIONS: dict[str, set[str]] = {
    "inProgress": {"active", "cancelled"},
    "active": {"expired", "terminated"},
    "expired": set(),    # terminal
    "terminated": set(), # terminal
    "cancelled": set(),  # terminal
}

VALID_QUOTE_COMPLETION_STATES: set[str] = {"accepted", "rejected"}
VALID_AGREEMENT_STATUS_CHANGE_STATES: set[str] = {"active", "expired", "terminated", "cancelled"}

VALID_QUOTE_ACTIONS: set[str] = {"add", "modify", "delete", "noChange"}
VALID_PRICE_TYPES: set[str] = {"recurring", "nonRecurring", "usage"}
VALID_AGREEMENT_TYPES: set[str] = {"commercial", "technical", "SLA"}
VALID_METRICS: set[str] = {"availability", "latency", "throughput", "mttr", "packetLoss", "jitter"}
VALID_METRIC_UNITS: set[str] = {"percent", "ms", "Mbps", "hours"}
VALID_CONFORMANCE_PERIODS: set[str] = {"daily", "weekly", "monthly"}


# ── QuoteItem schemas ──────────────────────────────────────────────────────────

class QuoteItemCreate(BaseModel):
    """Request body for adding a QuoteItem to a Quote."""

    action: str = Field(
        default="add",
        description=f"Line-item action. One of: {', '.join(sorted(VALID_QUOTE_ACTIONS))}",
    )
    quantity: int | None = Field(default=1, ge=1, description="Quantity of service units")
    item_price: Decimal | None = Field(
        default=None, ge=0, description="Unit price for this item"
    )
    price_type: str | None = Field(
        default=None,
        description=f"Pricing model. One of: {', '.join(sorted(VALID_PRICE_TYPES))}",
    )
    description: str | None = Field(default=None, description="Free-text item description")
    related_service_spec_id: str | None = Field(
        default=None, description="UUID of the linked ServiceSpecification (TMF633)"
    )


class QuoteItemResponse(BaseModel):
    """Response body for a QuoteItem."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    state: str
    quantity: int | None = None
    item_price: Decimal | None = None
    price_type: str | None = None
    description: str | None = None
    quote_id: str
    related_service_spec_id: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Quote schemas ──────────────────────────────────────────────────────────────

class QuoteCreate(BaseModel):
    """Request body for creating a Quote (TMF648 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable quote name")
    description: str | None = Field(default=None, description="Free-text description")
    category: str | None = Field(default=None, description="Quote category")
    requested_completion_date: datetime | None = Field(
        default=None, description="Requested completion datetime"
    )
    expected_fulfillment_start_date: datetime | None = Field(
        default=None, description="Expected start datetime"
    )
    related_service_spec_id: str | None = Field(
        default=None, description="UUID of the linked ServiceSpecification (TMF633)"
    )
    items: list[QuoteItemCreate] = Field(
        default_factory=list, description="Initial quote items"
    )


class QuotePatch(BaseModel):
    """Request body for partial update (PATCH) of a Quote."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    category: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description=(
            "Target state. Valid transitions: inProgress→pending|cancelled, "
            "pending→approved|rejected|inProgress, approved→accepted|cancelled"
        ),
    )
    requested_completion_date: datetime | None = Field(default=None)
    expected_fulfillment_start_date: datetime | None = Field(default=None)


class QuoteResponse(BaseEntity):
    """Response body for a Quote."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    category: str | None = None
    state: str
    quote_date: datetime
    requested_completion_date: datetime | None = None
    expected_fulfillment_start_date: datetime | None = None
    completion_date: datetime | None = None
    related_service_spec_id: str | None = None
    items: list[QuoteItemResponse] = []
    created_at: datetime
    updated_at: datetime


# ── ServiceLevelAgreement schemas ──────────────────────────────────────────────

class ServiceLevelAgreementCreate(BaseModel):
    """Request body for adding an SLA metric to an Agreement."""

    name: str = Field(..., min_length=1, max_length=255, description="SLA metric name")
    description: str | None = Field(default=None, description="Free-text description")
    metric: str = Field(
        ...,
        description=f"SLA metric type. One of: {', '.join(sorted(VALID_METRICS))}",
    )
    metric_threshold: Decimal = Field(..., gt=0, description="Threshold value for the metric")
    metric_unit: str | None = Field(
        default=None,
        description=f"Unit of measurement. One of: {', '.join(sorted(VALID_METRIC_UNITS))}",
    )
    conformance_period: str | None = Field(
        default=None,
        description=f"Measurement period. One of: {', '.join(sorted(VALID_CONFORMANCE_PERIODS))}",
    )


class ServiceLevelAgreementResponse(BaseModel):
    """Response body for a ServiceLevelAgreement."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    metric: str
    metric_threshold: Decimal
    metric_unit: str | None = None
    conformance_period: str | None = None
    agreement_id: str
    created_at: datetime
    updated_at: datetime


# ── Agreement schemas ──────────────────────────────────────────────────────────

class AgreementCreate(BaseModel):
    """Request body for creating an Agreement (TMF651 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable agreement name")
    description: str | None = Field(default=None, description="Free-text description")
    agreement_type: str | None = Field(
        default=None,
        description=f"Agreement type. One of: {', '.join(sorted(VALID_AGREEMENT_TYPES))}",
    )
    document_number: str | None = Field(default=None, description="Document reference number")
    version: str | None = Field(default="1.0", description="Agreement version string")
    start_date: datetime | None = Field(default=None, description="Agreement start datetime")
    end_date: datetime | None = Field(default=None, description="Agreement end datetime")
    related_service_spec_id: str | None = Field(
        default=None, description="UUID of the linked ServiceSpecification (TMF633)"
    )
    related_quote_id: str | None = Field(
        default=None, description="UUID of the linked Quote (TMF648)"
    )
    related_service_id: str | None = Field(
        default=None, description="UUID of the linked Service instance (TMF638)"
    )
    slas: list[ServiceLevelAgreementCreate] = Field(
        default_factory=list, description="Initial SLA metrics"
    )


class AgreementPatch(BaseModel):
    """Request body for partial update (PATCH) of an Agreement."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    agreement_type: str | None = Field(default=None)
    document_number: str | None = Field(default=None)
    version: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description=(
            "Target state. Valid transitions: inProgress→active|cancelled, "
            "active→expired|terminated"
        ),
    )
    start_date: datetime | None = Field(default=None)
    end_date: datetime | None = Field(default=None)


class AgreementResponse(BaseEntity):
    """Response body for an Agreement."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    agreement_type: str | None = None
    state: str
    document_number: str | None = None
    version: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status_change_date: datetime | None = None
    related_service_spec_id: str | None = None
    related_quote_id: str | None = None
    related_service_id: str | None = None
    slas: list[ServiceLevelAgreementResponse] = []
    created_at: datetime
    updated_at: datetime
