"""Base Pydantic schema with common SID / TMF hypermedia fields."""

from pydantic import BaseModel, ConfigDict, Field


class BaseEntity(BaseModel):
    """Common SID entity fields present on every TMF resource representation."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )

    id: str | None = Field(default=None, description="Unique identifier of the entity")
    href: str | None = Field(
        default=None,
        description="Hyperlink reference to the entity (self-link)",
    )
    name: str | None = Field(default=None, description="Human-readable name")
    description: str | None = Field(default=None, description="Free-text description")

    # TMF polymorphism / schema fields
    type: str | None = Field(
        default=None,
        alias="@type",
        description="Concrete type name (polymorphism discriminator)",
    )
    base_type: str | None = Field(
        default=None,
        alias="@baseType",
        description="Base type name when using inheritance",
    )
    schema_location: str | None = Field(
        default=None,
        alias="@schemaLocation",
        description="URI to the JSON Schema for this resource",
    )
