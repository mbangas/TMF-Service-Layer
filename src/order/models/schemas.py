"""Pydantic schemas for TMF641 Service Order Management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity


# ── ServiceOrderItem ──────────────────────────────────────────────────────────

class ServiceOrderItemBase(BaseModel):
    """Shared fields for ServiceOrderItem create / response."""

    order_item_id: str = Field(..., min_length=1, max_length=64, description="Client-assigned sequence label")
    action: str = Field(
        default="add",
        pattern="^(add|modify|delete|noChange)$",
        description="Order item action: add | modify | delete | noChange",
    )
    state: str | None = Field(default=None, description="Item lifecycle state")
    quantity: int = Field(default=1, ge=1, description="Quantity of service instances")

    # Service specification reference
    service_spec_id: str | None = Field(default=None, description="UUID of the referenced ServiceSpecification")
    service_spec_href: str | None = Field(default=None, description="Href of the referenced ServiceSpecification")
    service_spec_name: str | None = Field(default=None, description="Name of the referenced ServiceSpecification")

    # Service
    service_name: str | None = Field(default=None, description="Human-readable name for the service instance")
    service_description: str | None = Field(default=None, description="Free-text service description")
    note: str | None = Field(default=None, description="Order item notes")


class ServiceOrderItemCreate(ServiceOrderItemBase):
    """Request body for creating a ServiceOrderItem (nested in ServiceOrderCreate)."""

    pass


class ServiceOrderItemResponse(ServiceOrderItemBase):
    """Response body for a ServiceOrderItem."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    service_order_id: str
    created_at: datetime
    updated_at: datetime


# ── ServiceOrder ──────────────────────────────────────────────────────────────

class ServiceOrderCreate(BaseModel):
    """Request body for creating a ServiceOrder (TMF641 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable order name")
    description: str | None = Field(default=None, description="Free-text description")
    category: str | None = Field(default=None, description="Order category")
    priority: str | None = Field(default=None, description="Order priority (e.g. '1', 'high')")
    external_id: str | None = Field(default=None, description="External system reference")
    requested_start_date: datetime | None = Field(default=None, description="Requested start date")
    requested_completion_date: datetime | None = Field(default=None, description="Requested completion date")

    order_item: list[ServiceOrderItemCreate] = Field(
        default_factory=list,
        description="Ordered list of service order items",
    )

    # TMF annotation fields
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceOrderPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceOrder."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    category: str | None = Field(default=None)
    priority: str | None = Field(default=None)
    external_id: str | None = Field(default=None)
    state: str | None = Field(default=None, description="Lifecycle state transition target")
    requested_start_date: datetime | None = Field(default=None)
    requested_completion_date: datetime | None = Field(default=None)
    expected_completion_date: datetime | None = Field(default=None)
    note: str | None = Field(default=None)

    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceOrderResponse(BaseEntity):
    """Response body for a ServiceOrder resource (TMF641)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    external_id: str | None = None
    priority: str | None = None
    category: str | None = None
    state: str = "acknowledged"

    order_date: datetime | None = None
    completion_date: datetime | None = None
    requested_start_date: datetime | None = None
    requested_completion_date: datetime | None = None
    expected_completion_date: datetime | None = None
    start_date: datetime | None = None

    note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    order_item: list[ServiceOrderItemResponse] = Field(default_factory=list)
