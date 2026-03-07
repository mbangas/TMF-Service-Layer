"""Pydantic schemas for TMF653 Service Test Management.

Covers three resources:
  - ServiceTestSpecification — test templates
  - ServiceTest              — test run instances
  - TestMeasure              — nested metric results (child of ServiceTest)
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity

# ── State machine constants ───────────────────────────────────────────────────

VALID_TEST_MEASURE_RESULTS = {"pass", "fail", "inconclusive"}

TEST_SPEC_TRANSITIONS: dict[str, set[str]] = {
    "active": {"retired"},
    "retired": {"obsolete"},
    "obsolete": set(),  # terminal
}

TEST_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"inProgress", "cancelled"},
    "inProgress": {"completed", "failed", "cancelled"},
    "completed": set(),   # terminal
    "failed": set(),      # terminal
    "cancelled": set(),   # terminal
}

DELETABLE_SPEC_STATES: set[str] = {"obsolete"}
DELETABLE_TEST_STATES: set[str] = {"completed", "failed", "cancelled"}


# ── TestMeasure schemas ───────────────────────────────────────────────────────

class TestMeasureCreate(BaseModel):
    """Request body for recording a TestMeasure (POST .../testMeasure)."""

    metric_name: str = Field(..., min_length=1, max_length=255, description="Metric identifier")
    metric_value: float | None = Field(default=None, description="Measured value")
    unit_of_measure: str | None = Field(
        default=None, description="Unit of the metric (e.g. ms, Mbps, %)"
    )
    result: str | None = Field(
        default=None,
        description=f"Qualitative result. One of: {', '.join(sorted(VALID_TEST_MEASURE_RESULTS))}",
    )
    captured_at: datetime | None = Field(
        default=None, description="Timestamp when the metric was captured"
    )


class TestMeasureResponse(BaseModel):
    """Response body for a TestMeasure."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    service_test_id: str
    metric_name: str
    metric_value: float | None = None
    unit_of_measure: str | None = None
    result: str | None = None
    captured_at: datetime | None = None


# ── ServiceTestSpecification schemas ─────────────────────────────────────────

class ServiceTestSpecificationCreate(BaseModel):
    """Request body for creating a ServiceTestSpecification (TMF653 POST)."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Human-readable specification name"
    )
    description: str | None = Field(default=None, description="Free-text description")
    test_type: str | None = Field(
        default=None,
        description="Test category (e.g. connectivity, performance, functional)",
    )
    version: str | None = Field(default=None, description="Specification version string")
    valid_for_start: datetime | None = Field(
        default=None, description="Start of the validity period"
    )
    valid_for_end: datetime | None = Field(
        default=None, description="End of the validity period"
    )
    service_spec_id: str | None = Field(
        default=None,
        description="Optional UUID of the related ServiceSpecification (TMF633)",
    )


class ServiceTestSpecificationPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceTestSpecification."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description="Target state. Valid transitions: active→retired, retired→obsolete",
    )
    test_type: str | None = Field(default=None)
    version: str | None = Field(default=None)
    valid_for_start: datetime | None = Field(default=None)
    valid_for_end: datetime | None = Field(default=None)


class ServiceTestSpecificationResponse(BaseEntity):
    """Response body for a ServiceTestSpecification."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    state: str
    test_type: str | None = None
    version: str | None = None
    valid_for_start: datetime | None = None
    valid_for_end: datetime | None = None
    service_spec_id: str | None = None
    created_at: datetime
    updated_at: datetime


# ── ServiceTest schemas ───────────────────────────────────────────────────────

class ServiceTestCreate(BaseModel):
    """Request body for creating a ServiceTest (TMF653 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable test name")
    description: str | None = Field(default=None, description="Free-text description")
    mode: str | None = Field(
        default=None,
        description="Execution mode: automated | manual",
    )
    service_id: str = Field(
        ..., description="UUID of the target Service instance (TMF638)"
    )
    test_spec_id: str | None = Field(
        default=None,
        description="Optional UUID of the ServiceTestSpecification (TMF653) to use",
    )


class ServiceTestPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceTest."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description=(
            "Target state. Valid transitions: "
            "planned→inProgress|cancelled, "
            "inProgress→completed|failed|cancelled"
        ),
    )
    mode: str | None = Field(default=None)


class ServiceTestResponse(BaseEntity):
    """Response body for a ServiceTest (includes embedded TestMeasure list)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    state: str
    mode: str | None = None
    start_date_time: datetime | None = None
    end_date_time: datetime | None = None
    service_id: str
    test_spec_id: str | None = None
    measures: list[TestMeasureResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
