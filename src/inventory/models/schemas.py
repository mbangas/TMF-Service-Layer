"""Pydantic schemas for TMF638 Service Inventory Management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity

# Valid TMF638 service lifecycle states (§7.1.3)
VALID_SERVICE_STATES = {
    "feasibilityChecked",
    "designed",
    "reserved",
    "inactive",
    "active",
    "terminated",
}


# ── ServiceCharacteristic ─────────────────────────────────────────────────────

class ServiceCharacteristicBase(BaseModel):
    """Shared fields for ServiceCharacteristic create / response."""

    name: str = Field(..., min_length=1, max_length=255, description="Characteristic name")
    value: str | None = Field(default=None, description="Current value of the characteristic")
    value_type: str | None = Field(default=None, description="Data type of the value")


class ServiceCharacteristicCreate(ServiceCharacteristicBase):
    """Request body for creating a service characteristic."""

    pass


class ServiceCharacteristicResponse(ServiceCharacteristicBase):
    """Response body for a service characteristic."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    service_id: str
    created_at: datetime
    updated_at: datetime


# ── Service ───────────────────────────────────────────────────────────────────

class ServiceCreate(BaseModel):
    """Request body for creating a Service instance (TMF638 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable service name")
    description: str | None = Field(default=None, description="Free-text description")
    service_type: str | None = Field(default=None, description="CFS or RFS classification")
    state: str = Field(
        default="inactive",
        description=(
            "Initial lifecycle state. "
            "Allowed entry states: feasibilityChecked, designed, reserved, inactive, active."
        ),
    )
    start_date: datetime | None = Field(default=None, description="When the service started")
    end_date: datetime | None = Field(default=None, description="When the service is expected to end")

    # Cross-domain references
    service_spec_id: str | None = Field(
        default=None, description="UUID of the backing ServiceSpecification (TMF633)"
    )
    service_order_id: str | None = Field(
        default=None, description="UUID of the originating ServiceOrder (TMF641)"
    )

    service_characteristic: list[ServiceCharacteristicCreate] = Field(
        default_factory=list,
        description="Runtime characteristic values for this service instance",
    )

    # TMF annotation fields
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServicePatch(BaseModel):
    """Request body for partial update (PATCH) of a Service instance."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    service_type: str | None = Field(default=None)
    state: str | None = Field(default=None, description="Target lifecycle state")
    start_date: datetime | None = Field(default=None)
    end_date: datetime | None = Field(default=None)

    # TMF annotation fields
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceResponse(BaseEntity):
    """Response body for a Service instance (TMF638 GET / POST / PATCH)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    service_type: str | None = None
    state: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    # Cross-domain references
    service_spec_id: str | None = None
    service_order_id: str | None = None

    service_characteristic: list[ServiceCharacteristicResponse] = Field(
        default_factory=list,
        description="Runtime characteristic values",
    )

    created_at: datetime | None = None
    updated_at: datetime | None = None
