"""Pydantic schemas for TMF642 Alarm Management, TMF628 Performance Management,
and TMF657 Service Level Management.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity

# ── State machine constants ────────────────────────────────────────────────────

VALID_ALARM_SEVERITIES = {"critical", "major", "minor", "warning", "indeterminate"}

ALARM_TRANSITIONS: dict[str, set[str]] = {
    "raised": {"acknowledged"},
    "acknowledged": {"cleared"},
    "cleared": set(),  # terminal
}

MEASUREMENT_TRANSITIONS: dict[str, set[str]] = {
    "scheduled": {"completed", "failed"},
    "completed": set(),  # terminal
    "failed": set(),  # terminal
}

# Note: violated ↔ active transition is only done by check_violations, not PATCH
SLO_TRANSITIONS: dict[str, set[str]] = {
    "active": {"suspended"},
    "violated": {"active", "suspended"},
    "suspended": {"active"},
}

DELETABLE_ALARM_STATES: set[str] = {"cleared"}
DELETABLE_MEASUREMENT_STATES: set[str] = {"completed", "failed"}
DELETABLE_SLO_STATES: set[str] = {"suspended"}


# ── Alarm schemas ──────────────────────────────────────────────────────────────

class AlarmCreate(BaseModel):
    """Request body for creating an Alarm (TMF642 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable alarm name")
    description: str | None = Field(default=None, description="Free-text description")
    alarm_type: str | None = Field(default=None, description="Alarm type classification")
    severity: str | None = Field(
        default=None,
        description=f"Alarm severity. One of: {', '.join(sorted(VALID_ALARM_SEVERITIES))}",
    )
    probable_cause: str | None = Field(default=None, description="Probable cause of the alarm")
    specific_problem: str | None = Field(default=None, description="Specific problem description")
    service_id: str = Field(..., description="UUID of the target Service instance (TMF638)")
    raised_at: datetime | None = Field(default=None, description="When the alarm was raised")


class AlarmPatch(BaseModel):
    """Request body for partial update (PATCH) of an Alarm."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description="Target state. Valid transitions: raised→acknowledged, acknowledged→cleared",
    )
    severity: str | None = Field(default=None)
    probable_cause: str | None = Field(default=None)
    specific_problem: str | None = Field(default=None)


class AlarmResponse(BaseEntity):
    """Response body for an Alarm."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    state: str
    alarm_type: str | None = None
    severity: str | None = None
    probable_cause: str | None = None
    specific_problem: str | None = None
    service_id: str
    raised_at: datetime | None = None
    acknowledged_at: datetime | None = None
    cleared_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ── Performance Measurement schemas ───────────────────────────────────────────

class PerformanceMeasurementCreate(BaseModel):
    """Request body for creating a PerformanceMeasurement (TMF628 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable measurement name")
    description: str | None = Field(default=None, description="Free-text description")
    metric_name: str = Field(..., min_length=1, max_length=255, description="Metric identifier")
    metric_value: float | None = Field(default=None, description="Measured metric value")
    unit_of_measure: str | None = Field(default=None, description="Unit of the metric (e.g. Mbps, ms)")
    granularity: str | None = Field(
        default=None,
        description="Measurement granularity: minutely | hourly | daily | weekly | monthly",
    )
    service_id: str = Field(..., description="UUID of the target Service instance (TMF638)")
    scheduled_at: datetime | None = Field(default=None, description="When the measurement was scheduled")


class PerformanceMeasurementPatch(BaseModel):
    """Request body for partial update (PATCH) of a PerformanceMeasurement."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description="Target state. Valid transitions: scheduled→completed|failed",
    )
    metric_value: float | None = Field(default=None, description="Measured metric value (set on completion)")
    unit_of_measure: str | None = Field(default=None)
    granularity: str | None = Field(default=None)
    completed_at: datetime | None = Field(default=None, description="When the measurement completed")


class PerformanceMeasurementResponse(BaseEntity):
    """Response body for a PerformanceMeasurement."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    state: str
    metric_name: str
    metric_value: float | None = None
    unit_of_measure: str | None = None
    granularity: str | None = None
    service_id: str
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ── Service Level Objective schemas ───────────────────────────────────────────

class ServiceLevelObjectiveCreate(BaseModel):
    """Request body for creating a ServiceLevelObjective (TMF657 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable SLO name")
    description: str | None = Field(default=None, description="Free-text description")
    metric_name: str = Field(..., min_length=1, max_length=255, description="Metric this SLO monitors")
    threshold_value: float | None = Field(default=None, description="Threshold that triggers a violation")
    direction: str | None = Field(
        default=None,
        description="'above' (alert when metric > threshold) or 'below' (alert when metric < threshold)",
    )
    tolerance: float | None = Field(default=None, description="Acceptable tolerance around the threshold")
    service_id: str = Field(..., description="UUID of the target Service instance (TMF638)")
    sls_id: str | None = Field(
        default=None,
        description="Optional UUID of the ServiceLevelSpecification (TMF633) this SLO implements",
    )


class ServiceLevelObjectivePatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceLevelObjective."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description=(
            "Target state. Valid manual transitions: active→suspended, "
            "violated→active|suspended, suspended→active. "
            "Transition to 'violated' is only performed automatically by check_violations."
        ),
    )
    threshold_value: float | None = Field(default=None)
    direction: str | None = Field(default=None)
    tolerance: float | None = Field(default=None)


class ServiceLevelObjectiveResponse(BaseEntity):
    """Response body for a ServiceLevelObjective."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    state: str
    metric_name: str
    threshold_value: float | None = None
    direction: str | None = None
    tolerance: float | None = None
    service_id: str
    sls_id: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Check-violations request/response ─────────────────────────────────────────

class CheckViolationsRequest(BaseModel):
    """Request body for POST /serviceLevel/check_violations."""

    service_id: str = Field(..., description="UUID of the Service instance to evaluate")
    metric_name: str = Field(..., min_length=1, max_length=255, description="Metric identifier to evaluate")
    metric_value: float = Field(..., description="Current measured value to compare against SLO thresholds")


class CheckViolationsResponse(BaseModel):
    """Response body for POST /serviceLevel/check_violations."""

    evaluated: int = Field(..., description="Number of active SLOs evaluated")
    violated: int = Field(..., description="Number of SLOs that transitioned to violated")
    slos: list[ServiceLevelObjectiveResponse] = Field(..., description="Updated state of all evaluated SLOs")
