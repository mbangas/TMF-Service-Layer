"""Pydantic schemas for TMF633 Service Catalog Management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity


# ── ServiceSpecCharacteristic ─────────────────────────────────────────────────

class ServiceSpecCharacteristicBase(BaseModel):
    """Shared fields for ServiceSpecCharacteristic create / update."""

    name: str = Field(..., min_length=1, max_length=255, description="Characteristic name")
    description: str | None = Field(default=None, description="Free-text description")
    value_type: str | None = Field(default=None, description="Data type of the characteristic value")
    is_unique: bool = Field(default=False, description="True if values must be unique")
    min_cardinality: int = Field(default=0, ge=0, description="Minimum number of values")
    max_cardinality: int = Field(default=1, ge=1, description="Maximum number of values")
    extensible: bool = Field(default=False, description="True if new values may be added")


class ServiceSpecCharacteristicCreate(ServiceSpecCharacteristicBase):
    """Request body for creating a characteristic."""

    pass


class ServiceSpecCharacteristicResponse(ServiceSpecCharacteristicBase):
    """Response body for a characteristic."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    service_spec_id: str
    created_at: datetime
    updated_at: datetime


# ── ServiceLevelSpecification ─────────────────────────────────────────────────

class ServiceLevelSpecBase(BaseModel):
    """Shared fields for ServiceLevelSpecification create / update."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    validity_period_start: str | None = None
    validity_period_end: str | None = None


class ServiceLevelSpecCreate(ServiceLevelSpecBase):
    """Request body for creating a service level specification."""

    pass


class ServiceLevelSpecResponse(ServiceLevelSpecBase):
    """Response body for a service level specification."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    service_spec_id: str
    created_at: datetime
    updated_at: datetime


# ── ServiceSpecification ──────────────────────────────────────────────────────

VALID_LIFECYCLE_STATUSES = {"draft", "active", "obsolete", "retired"}


class ServiceSpecificationCreate(BaseModel):
    """Request body for creating a ServiceSpecification (TMF633 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Specification name")
    description: str | None = Field(default=None, description="Free-text description")
    version: str | None = Field(default="1.0", description="Specification version string")
    is_bundle: bool = Field(default=False, description="True if this is a bundle of specifications")
    lifecycle_status: str = Field(
        default="draft",
        description="Lifecycle status: draft | active | obsolete | retired",
    )

    # Nested objects
    service_spec_characteristic: list[ServiceSpecCharacteristicCreate] = Field(
        default_factory=list
    )
    service_level_specification: list[ServiceLevelSpecCreate] = Field(
        default_factory=list
    )

    # TMF annotation fields
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceSpecificationUpdate(BaseModel):
    """Request body for full replacement (PUT) of a ServiceSpecification."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    version: str | None = None
    is_bundle: bool = False
    lifecycle_status: str = Field(default="draft")

    service_spec_characteristic: list[ServiceSpecCharacteristicCreate] = Field(
        default_factory=list
    )
    service_level_specification: list[ServiceLevelSpecCreate] = Field(
        default_factory=list
    )

    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceSpecificationPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceSpecification."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    version: str | None = None
    is_bundle: bool | None = None
    lifecycle_status: str | None = None

    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceSpecificationResponse(BaseEntity):
    """Response body for a ServiceSpecification resource (TMF633)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    version: str | None = None
    is_bundle: bool = False
    lifecycle_status: str = "draft"
    last_update: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    service_spec_characteristic: list[ServiceSpecCharacteristicResponse] = Field(
        default_factory=list
    )
    service_level_specification: list[ServiceLevelSpecResponse] = Field(
        default_factory=list
    )
