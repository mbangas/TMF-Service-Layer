"""SQLAlchemy ORM models for TMF633 Service Catalog Management (TMFC006)."""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db.base import Base, TimestampMixin

# ── Association tables (M2M) ──────────────────────────────────────────────────

# ServiceCatalog ↔ ServiceCategory
service_catalog_category = Table(
    "service_catalog_category",
    Base.metadata,
    Column(
        "catalog_id",
        String(36),
        ForeignKey("service_catalog.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        String(36),
        ForeignKey("service_category.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ServiceCategory ↔ ServiceCandidate
service_candidate_category = Table(
    "service_candidate_category",
    Base.metadata,
    Column(
        "candidate_id",
        String(36),
        ForeignKey("service_candidate.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        String(36),
        ForeignKey("service_category.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ServiceSpecCharacteristicOrm(Base, TimestampMixin):
    """Represents a configurable characteristic of a ServiceSpecification.

    Maps to the TMF633 ``ServiceSpecCharacteristic`` entity.
    """

    __tablename__ = "service_spec_characteristic"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_unique: Mapped[bool] = mapped_column(default=False, nullable=False)
    min_cardinality: Mapped[int] = mapped_column(default=0, nullable=False)
    max_cardinality: Mapped[int] = mapped_column(default=1, nullable=False)
    extensible: Mapped[bool] = mapped_column(default=False, nullable=False)

    # FK to parent specification
    service_spec_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_specification: Mapped["ServiceSpecificationOrm"] = relationship(
        back_populates="service_spec_characteristic"
    )
    characteristic_value_specification: Mapped[list["CharacteristicValueSpecificationOrm"]] = relationship(
        back_populates="service_spec_characteristic",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CharacteristicValueSpecificationOrm(Base, TimestampMixin):
    """Represents an allowed value for a ServiceSpecCharacteristic.

    Maps to the TMF633 ``CharacteristicValueSpecification`` entity.
    """

    __tablename__ = "characteristic_value_specification"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    value_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_from: Mapped[str | None] = mapped_column(String(128), nullable=True)
    value_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    range_interval: Mapped[str | None] = mapped_column(String(64), nullable=True)
    regex: Mapped[str | None] = mapped_column(String(512), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)

    # FK to parent characteristic
    char_spec_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_spec_characteristic.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_spec_characteristic: Mapped["ServiceSpecCharacteristicOrm"] = relationship(
        back_populates="characteristic_value_specification"
    )


class ServiceLevelSpecificationOrm(Base, TimestampMixin):
    """Represents a Service Level Specification linked to a ServiceSpecification.

    Maps to the TMF633 ``ServiceLevelSpecification`` entity.
    """

    __tablename__ = "service_level_specification"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    validity_period_start: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validity_period_end: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # FK to parent specification
    service_spec_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_specification: Mapped["ServiceSpecificationOrm"] = relationship(
        back_populates="service_level_specification"
    )


class ServiceSpecificationOrm(Base, TimestampMixin):
    """SQLAlchemy model for TMF633 ``ServiceSpecification``.

    Lifecycle states: draft → active → obsolete → retired
    """

    __tablename__ = "service_specification"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        index=True,
    )
    is_bundle: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_update: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # TMF annotation fields
    type: Mapped[str | None] = mapped_column("type", String(128), nullable=True)
    base_type: Mapped[str | None] = mapped_column("base_type", String(128), nullable=True)
    schema_location: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationships
    service_spec_characteristic: Mapped[list[ServiceSpecCharacteristicOrm]] = relationship(
        back_populates="service_specification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    service_level_specification: Mapped[list[ServiceLevelSpecificationOrm]] = relationship(
        back_populates="service_specification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # Back-reference from ServiceCandidateOrm
    service_candidates: Mapped[list["ServiceCandidateOrm"]] = relationship(
        back_populates="service_specification",
        lazy="selectin",
    )


# ── ServiceCategory ───────────────────────────────────────────────────────────


class ServiceCategoryOrm(Base, TimestampMixin):
    """SQLAlchemy model for TMF633 ``ServiceCategory``.

    Supports hierarchical categorisation (parent/sub-categories).
    Lifecycle states: draft → active → obsolete → retired
    """

    __tablename__ = "service_category"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        index=True,
    )
    is_root: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_update: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Self-referencing hierarchy
    parent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_category.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent: Mapped["ServiceCategoryOrm | None"] = relationship(
        "ServiceCategoryOrm",
        back_populates="sub_categories",
        remote_side="ServiceCategoryOrm.id",
    )
    sub_categories: Mapped[list["ServiceCategoryOrm"]] = relationship(
        "ServiceCategoryOrm",
        back_populates="parent",
        lazy="noload",
    )

    # TMF annotation fields
    type: Mapped[str | None] = mapped_column("type", String(128), nullable=True)
    base_type: Mapped[str | None] = mapped_column("base_type", String(128), nullable=True)
    schema_location: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # M2M: ServiceCatalog ↔ ServiceCategory (back-reference — noload prevents circular cascade)
    catalogs: Mapped[list["ServiceCatalogOrm"]] = relationship(
        secondary=service_catalog_category,
        back_populates="categories",
        lazy="noload",
    )
    # M2M: ServiceCategory ↔ ServiceCandidate (back-reference — noload prevents circular cascade)
    service_candidates: Mapped[list["ServiceCandidateOrm"]] = relationship(
        secondary=service_candidate_category,
        back_populates="categories",
        lazy="noload",
    )


# ── ServiceCandidate ──────────────────────────────────────────────────────────


class ServiceCandidateOrm(Base, TimestampMixin):
    """SQLAlchemy model for TMF633 ``ServiceCandidate``.

    Links a ``ServiceSpecification`` to one or more ``ServiceCategory`` entries.
    Lifecycle states: draft → active → obsolete → retired
    """

    __tablename__ = "service_candidate"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        index=True,
    )
    last_update: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Optional FK to the ServiceSpecification this candidate represents
    service_spec_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    service_specification: Mapped["ServiceSpecificationOrm | None"] = relationship(
        back_populates="service_candidates",
        lazy="selectin",
    )

    # TMF annotation fields
    type: Mapped[str | None] = mapped_column("type", String(128), nullable=True)
    base_type: Mapped[str | None] = mapped_column("base_type", String(128), nullable=True)
    schema_location: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # M2M: ServiceCategory ↔ ServiceCandidate
    categories: Mapped[list[ServiceCategoryOrm]] = relationship(
        secondary=service_candidate_category,
        back_populates="service_candidates",
        lazy="selectin",
    )


# ── ServiceCatalog ────────────────────────────────────────────────────────────


class ServiceCatalogOrm(Base, TimestampMixin):
    """SQLAlchemy model for TMF633 ``ServiceCatalog``.

    Top-level catalog container; aggregates ``ServiceCategory`` entries.
    Lifecycle states: active → obsolete → retired
    """

    __tablename__ = "service_catalog"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        index=True,
    )
    last_update: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # TMF annotation fields
    type: Mapped[str | None] = mapped_column("type", String(128), nullable=True)
    base_type: Mapped[str | None] = mapped_column("base_type", String(128), nullable=True)
    schema_location: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # M2M: ServiceCatalog ↔ ServiceCategory
    categories: Mapped[list[ServiceCategoryOrm]] = relationship(
        secondary=service_catalog_category,
        back_populates="catalogs",
        lazy="selectin",
    )
