"""Pydantic schemas for TMF633 Service Catalog Management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity


# ── CharacteristicValueSpecification ─────────────────────────────────────────

class CharacteristicValueSpecBase(BaseModel):
    """Shared fields for CharacteristicValueSpecification create / update."""

    value_type: str | None = Field(default=None, description="Data type of the allowed value")
    value: str | None = Field(default=None, description="Specific allowed value")
    value_from: str | None = Field(default=None, description="Start of an allowed value range")
    value_to: str | None = Field(default=None, description="End of an allowed value range")
    range_interval: str | None = Field(default=None, description="Range interval type (open, closed, etc.)")
    regex: str | None = Field(default=None, description="Regular expression describing allowed values")
    unit_of_measure: str | None = Field(default=None, description="Unit of measure for the value")
    is_default: bool = Field(default=False, description="True if this is the default value")


class CharacteristicValueSpecCreate(CharacteristicValueSpecBase):
    """Request body for creating a CharacteristicValueSpecification."""

    pass


class CharacteristicValueSpecResponse(CharacteristicValueSpecBase):
    """Response body for a CharacteristicValueSpecification."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    char_spec_id: str
    created_at: datetime
    updated_at: datetime


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

    characteristic_value_specification: list[CharacteristicValueSpecCreate] = Field(
        default_factory=list,
        description="Allowed values for this characteristic",
    )


class ServiceSpecCharacteristicPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceSpecCharacteristic."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    value_type: str | None = None
    is_unique: bool | None = None
    min_cardinality: int | None = Field(default=None, ge=0)
    max_cardinality: int | None = Field(default=None, ge=1)
    extensible: bool | None = None


class ServiceSpecCharacteristicResponse(ServiceSpecCharacteristicBase):
    """Response body for a characteristic."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    service_spec_id: str
    characteristic_value_specification: list[CharacteristicValueSpecResponse] = Field(
        default_factory=list
    )
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
    spec_relationships: list[ServiceSpecRelationshipResponse] = Field(
        default_factory=list,
        description="TMF633 ServiceSpecRelationship entries for this specification",
    )


# ── ServiceSpecRelationship ──────────────────────────────────────────────────

VALID_RELATIONSHIP_TYPES = {"dependency", "isContainedIn", "isReplacedBy", "hasPart"}


class ServiceSpecRelationshipCreate(BaseModel):
    """Request body for creating a ServiceSpecRelationship (TMF633)."""

    relationship_type: str = Field(
        ...,
        description="Relationship type: dependency | isContainedIn | isReplacedBy | hasPart",
    )
    related_spec_id: str = Field(..., description="UUID of the related ServiceSpecification")
    related_spec_name: str | None = Field(default=None, description="Name of the related spec")
    related_spec_href: str | None = Field(default=None, description="Href of the related spec")


class ServiceSpecRelationshipResponse(BaseModel):
    """Response body for a ServiceSpecRelationship."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    spec_id: str
    relationship_type: str
    related_spec_id: str
    related_spec_name: str | None = None
    related_spec_href: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Reference types (embedded in responses) ───────────────────────────────────

class ServiceSpecificationRef(BaseModel):
    """Lightweight reference to a ServiceSpecification embedded in responses."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    href: str | None = None
    name: str | None = None
    version: str | None = None
    type: str | None = Field(default=None, alias="@type")


class ServiceCategoryRef(BaseModel):
    """Lightweight reference to a ServiceCategory embedded in responses."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    href: str | None = None
    name: str | None = None
    type: str | None = Field(default=None, alias="@type")


class ServiceCandidateRef(BaseModel):
    """Lightweight reference to a ServiceCandidate embedded in responses."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    href: str | None = None
    name: str | None = None
    type: str | None = Field(default=None, alias="@type")


# ── ServiceCategory ───────────────────────────────────────────────────────────

class ServiceCategoryCreate(BaseModel):
    """Request body for creating a ServiceCategory (TMF633 POST)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    version: str | None = Field(default="1.0")
    lifecycle_status: str = Field(default="active")
    is_root: bool = Field(default=True)
    parent_id: str | None = Field(default=None, description="ID of the parent category")
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")


class ServiceCategoryUpdate(BaseModel):
    """Request body for full replacement (PUT) of a ServiceCategory."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    version: str | None = None
    lifecycle_status: str = Field(default="active")
    is_root: bool = False
    parent_id: str | None = None
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")


class ServiceCategoryPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceCategory."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    version: str | None = None
    lifecycle_status: str | None = None
    is_root: bool | None = None
    parent_id: str | None = None
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")


class ServiceCategoryResponse(BaseEntity):
    """Response body for a ServiceCategory resource (TMF633)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    version: str | None = None
    lifecycle_status: str = "active"
    is_root: bool = True
    parent_id: str | None = None
    last_update: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    sub_categories: list["ServiceCategoryRef"] = Field(default_factory=list)
    service_candidates: list["ServiceCandidateRef"] = Field(default_factory=list)


# ── ServiceCandidate ──────────────────────────────────────────────────────────

class ServiceCandidateCreate(BaseModel):
    """Request body for creating a ServiceCandidate (TMF633 POST)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    version: str | None = Field(default="1.0")
    lifecycle_status: str = Field(default="active")
    service_spec_id: str | None = Field(
        default=None,
        description="ID of the ServiceSpecification this candidate represents",
    )
    category_ids: list[str] = Field(
        default_factory=list,
        description="IDs of ServiceCategory resources to associate",
    )
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")


class ServiceCandidateUpdate(BaseModel):
    """Request body for full replacement (PUT) of a ServiceCandidate."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    version: str | None = None
    lifecycle_status: str = Field(default="active")
    service_spec_id: str | None = None
    category_ids: list[str] = Field(default_factory=list)
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")


class ServiceCandidatePatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceCandidate."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    version: str | None = None
    lifecycle_status: str | None = None
    service_spec_id: str | None = None
    category_ids: list[str] | None = None
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")


class ServiceCandidateResponse(BaseEntity):
    """Response body for a ServiceCandidate resource (TMF633)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    version: str | None = None
    lifecycle_status: str = "active"
    last_update: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    service_specification: ServiceSpecificationRef | None = None
    categories: list[ServiceCategoryRef] = Field(default_factory=list)


# ── ServiceCatalog ────────────────────────────────────────────────────────────

class ServiceCatalogCreate(BaseModel):
    """Request body for creating a ServiceCatalog (TMF633 POST)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    version: str | None = Field(default="1.0")
    lifecycle_status: str = Field(default="active")
    category_ids: list[str] = Field(
        default_factory=list,
        description="IDs of ServiceCategory resources to include in this catalog",
    )
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")


class ServiceCatalogUpdate(BaseModel):
    """Request body for full replacement (PUT) of a ServiceCatalog."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    version: str | None = None
    lifecycle_status: str = Field(default="active")
    category_ids: list[str] = Field(default_factory=list)
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")


class ServiceCatalogPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceCatalog."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    version: str | None = None
    lifecycle_status: str | None = None
    category_ids: list[str] | None = None
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")


class ServiceCatalogResponse(BaseEntity):
    """Response body for a ServiceCatalog resource (TMF633)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    version: str | None = None
    lifecycle_status: str = "active"
    last_update: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    categories: list[ServiceCategoryRef] = Field(default_factory=list)


# ── Forward-reference resolution ──────────────────────────────────────────────

ServiceCategoryResponse.model_rebuild()

