"""Pydantic schemas for TMF640 Service Activation & Configuration."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity

# Valid TMF640 job types
VALID_JOB_TYPES = {"provision", "activate", "modify", "deactivate", "terminate"}

# Valid job lifecycle states
VALID_JOB_STATES = {"accepted", "running", "succeeded", "failed", "cancelled"}

# Valid state transitions: {from_state: {allowed_to_states}}
JOB_TRANSITIONS: dict[str, set[str]] = {
    "accepted": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    # Terminal states — no further transitions
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}

# Valid Service states for each job type (pre-condition check)
JOB_TYPE_VALID_SERVICE_STATES: dict[str, set[str]] = {
    "provision": {"inactive"},
    "activate": {"inactive"},
    "modify": {"active"},
    "deactivate": {"active"},
    "terminate": {"active", "inactive"},
}

# Resulting Service state on job succeeded
SERVICE_STATE_ON_SUCCESS: dict[str, str] = {
    "provision": "active",
    "activate": "active",
    "modify": "active",
    "deactivate": "inactive",
    "terminate": "terminated",
}

# States that permit deletion
DELETABLE_JOB_STATES = {"failed", "cancelled"}


# ── ServiceConfigurationParam ─────────────────────────────────────────────────

class ServiceConfigurationParamCreate(BaseModel):
    """Request body for a configuration parameter attached to a job."""

    name: str = Field(..., min_length=1, max_length=255, description="Parameter name")
    value: str | None = Field(default=None, description="Parameter value")
    value_type: str | None = Field(default=None, description="Data type of the value")


class ServiceConfigurationParamResponse(ServiceConfigurationParamCreate):
    """Response body for a configuration parameter."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    job_id: str
    created_at: datetime
    updated_at: datetime


# ── ServiceActivationJob ──────────────────────────────────────────────────────

class ServiceActivationJobCreate(BaseModel):
    """Request body for creating a ServiceActivationJob (TMF640 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable job name")
    description: str | None = Field(default=None, description="Free-text description")
    job_type: str = Field(
        ...,
        description=f"Type of activation action. One of: {', '.join(sorted(VALID_JOB_TYPES))}",
    )
    service_id: str = Field(
        ...,
        description="UUID of the target Service instance (TMF638)",
    )
    mode: str | None = Field(
        default=None,
        description="Execution mode: immediate or deferred",
    )
    start_mode: str | None = Field(
        default=None,
        description="Start mode: automatic or manual",
    )
    scheduled_start_date: datetime | None = Field(
        default=None,
        description="When the job should start (deferred mode)",
    )
    scheduled_completion_date: datetime | None = Field(
        default=None,
        description="Expected completion date",
    )
    params: list[ServiceConfigurationParamCreate] = Field(
        default_factory=list,
        description="Configuration parameters to apply when the job succeeds",
    )

    # TMF annotation fields
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceActivationJobPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceActivationJob."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description=f"Target lifecycle state. Valid transitions: accepted→running|cancelled, running→succeeded|failed|cancelled",
    )
    mode: str | None = Field(default=None)
    start_mode: str | None = Field(default=None)
    scheduled_start_date: datetime | None = Field(default=None)
    scheduled_completion_date: datetime | None = Field(default=None)
    actual_start_date: datetime | None = Field(default=None)
    actual_completion_date: datetime | None = Field(default=None)
    error_message: str | None = Field(default=None, description="Error detail (on failure)")

    # TMF annotation fields
    type: str | None = Field(default=None, alias="@type")
    base_type: str | None = Field(default=None, alias="@baseType")
    schema_location: str | None = Field(default=None, alias="@schemaLocation")

    model_config = ConfigDict(populate_by_name=True)


class ServiceActivationJobResponse(BaseEntity):
    """Response body for a ServiceActivationJob (TMF640 GET / POST / PATCH)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    job_type: str | None = None
    state: str | None = None
    mode: str | None = None
    start_mode: str | None = None
    service_id: str | None = None
    scheduled_start_date: datetime | None = None
    scheduled_completion_date: datetime | None = None
    actual_start_date: datetime | None = None
    actual_completion_date: datetime | None = None
    error_message: str | None = None

    params: list[ServiceConfigurationParamResponse] = Field(
        default_factory=list,
        description="Configuration parameters attached to this job",
    )

    created_at: datetime | None = None
    updated_at: datetime | None = None
