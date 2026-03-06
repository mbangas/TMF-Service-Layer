"""Pydantic schemas for TMF645 Service Qualification Management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity

# Valid qualification lifecycle states
VALID_QUALIFICATION_STATES = {"acknowledged", "inProgress", "accepted", "rejected", "cancelled"}

# Valid qualification item result states
VALID_ITEM_STATES = {"approved", "rejected", "unableToProvide"}

# Valid state transitions: {from_state: {allowed_to_states}}
QUALIFICATION_TRANSITIONS: dict[str, set[str]] = {
    "acknowledged": {"inProgress", "cancelled"},
    "inProgress": {"accepted", "rejected", "cancelled"},
    # Terminal states — no further transitions
    "accepted": set(),
    "rejected": set(),
    "cancelled": set(),
}

# States that permit deletion
DELETABLE_QUALIFICATION_STATES = {"accepted", "rejected", "cancelled"}


# ── ServiceQualificationItem ──────────────────────────────────────────────────

class ServiceQualificationItemCreate(BaseModel):
    """Request body for a qualification item (nested within a qualification request)."""

    service_spec_id: str | None = Field(
        default=None,
        description="UUID of the target ServiceSpecification (TMF633). Optional.",
    )
    state: str | None = Field(
        default=None,
        description=(
            f"Initial result state. One of: {', '.join(sorted(VALID_ITEM_STATES))}. "
            "Defaults to 'approved' if omitted."
        ),
    )
    qualifier_message: str | None = Field(
        default=None,
        description="Human-readable qualification result message",
    )
    termination_error: str | None = Field(
        default=None,
        description="Error detail when state is 'rejected' or 'unableToProvide'",
    )


class ServiceQualificationItemResponse(BaseModel):
    """Response body for a qualification item."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    qualification_id: str
    service_spec_id: str | None = None
    state: str
    qualifier_message: str | None = None
    termination_error: str | None = None
    created_at: datetime
    updated_at: datetime


# ── ServiceQualification ──────────────────────────────────────────────────────

class ServiceQualificationCreate(BaseModel):
    """Request body for creating a ServiceQualification (TMF645 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable qualification name")
    description: str | None = Field(default=None, description="Free-text description")

    expected_qualification_date: datetime | None = Field(
        default=None,
        description="When the qualification result is expected",
    )
    expiration_date: datetime | None = Field(
        default=None,
        description="Date after which the qualification result is no longer valid",
    )

    items: list[ServiceQualificationItemCreate] = Field(
        default_factory=list,
        description="Qualification items — one per service specification to check",
    )

    # TMF annotation fields
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceQualificationPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceQualification."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description=(
            "Target lifecycle state. Valid transitions: "
            "acknowledged→inProgress|cancelled, "
            "inProgress→accepted|rejected|cancelled"
        ),
    )
    expected_qualification_date: datetime | None = Field(default=None)
    expiration_date: datetime | None = Field(default=None)

    # TMF annotation fields
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceQualificationResponse(BaseEntity):
    """Response body for a ServiceQualification (TMF645 GET / POST / PATCH)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    state: str | None = None
    expected_qualification_date: datetime | None = None
    expiration_date: datetime | None = None

    items: list[ServiceQualificationItemResponse] = Field(
        default_factory=list,
        description="Qualification items attached to this request",
    )

    created_at: datetime | None = None
    updated_at: datetime | None = None
