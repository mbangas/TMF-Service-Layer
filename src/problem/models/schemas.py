"""Pydantic schemas for TMF621 Trouble Ticket Management and TMF656 Service Problem Management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models.base_entity import BaseEntity

# ── State machine constants ────────────────────────────────────────────────────

TICKET_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"inProgress"},
    "inProgress": {"pending", "resolved"},
    "pending": {"inProgress", "resolved"},
    "resolved": {"closed"},
    "closed": set(),  # terminal
}

PROBLEM_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"confirmed", "rejected"},
    "confirmed": {"active", "rejected"},
    "active": {"resolved"},
    "resolved": {"closed"},
    "rejected": set(),  # terminal
    "closed": set(),   # terminal
}

VALID_TICKET_SEVERITIES: set[str] = {"critical", "major", "minor", "warning"}
VALID_PROBLEM_IMPACTS: set[str] = {
    "criticalSystemImpact", "localImpact", "serviceImpact", "noImpact"
}


# ── TroubleTicketNote schemas ──────────────────────────────────────────────────

class TroubleTicketNoteCreate(BaseModel):
    """Request body for adding a note to a TroubleTicket."""

    text: str = Field(..., min_length=1, description="Note content")
    author: str | None = Field(default=None, description="Author name or system identifier")


class TroubleTicketNoteResponse(BaseModel):
    """Response body for a TroubleTicketNote."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    text: str
    author: str | None = None
    note_date: datetime
    ticket_id: str


# ── TroubleTicket schemas ──────────────────────────────────────────────────────

class TroubleTicketCreate(BaseModel):
    """Request body for creating a TroubleTicket (TMF621 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable ticket name")
    description: str | None = Field(default=None, description="Free-text description")
    severity: str | None = Field(
        default=None,
        description=f"Ticket severity. One of: {', '.join(sorted(VALID_TICKET_SEVERITIES))}",
    )
    priority: int | None = Field(default=None, ge=1, le=4, description="Priority 1 (highest) to 4 (lowest)")
    ticket_type: str | None = Field(
        default=None,
        description="serviceFailure | servicePerformanceDegradation | scheduledMaintenance | others",
    )
    expected_resolution_date: datetime | None = Field(
        default=None, description="Target resolution datetime"
    )
    related_service_id: str | None = Field(
        default=None, description="UUID of the affected Service instance (TMF638)"
    )
    related_alarm_id: str | None = Field(
        default=None, description="UUID of the linked Alarm (TMF642)"
    )
    notes: list[TroubleTicketNoteCreate] = Field(
        default_factory=list, description="Initial notes to attach"
    )


class TroubleTicketPatch(BaseModel):
    """Request body for partial update (PATCH) of a TroubleTicket."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description=(
            "Target state. Valid transitions: submitted→inProgress, "
            "inProgress→pending|resolved, pending→inProgress|resolved, resolved→closed"
        ),
    )
    severity: str | None = Field(default=None)
    priority: int | None = Field(default=None, ge=1, le=4)
    ticket_type: str | None = Field(default=None)
    resolution: str | None = Field(default=None)
    expected_resolution_date: datetime | None = Field(default=None)


class TroubleTicketResponse(BaseEntity):
    """Response body for a TroubleTicket."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    state: str
    severity: str | None = None
    priority: int | None = None
    ticket_type: str | None = None
    resolution: str | None = None
    expected_resolution_date: datetime | None = None
    resolution_date: datetime | None = None
    related_service_id: str | None = None
    related_alarm_id: str | None = None
    notes: list[TroubleTicketNoteResponse] = []
    created_at: datetime
    updated_at: datetime


# ── ServiceProblem schemas ─────────────────────────────────────────────────────

class ServiceProblemCreate(BaseModel):
    """Request body for creating a ServiceProblem (TMF656 POST)."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable problem name")
    description: str | None = Field(default=None, description="Free-text description")
    category: str | None = Field(default=None, description="Problem category")
    impact: str | None = Field(
        default=None,
        description=f"Business impact. One of: {', '.join(sorted(VALID_PROBLEM_IMPACTS))}",
    )
    priority: int | None = Field(default=None, ge=1, le=4, description="Priority 1 (highest) to 4 (lowest)")
    root_cause: str | None = Field(default=None, description="Root cause analysis text")
    expected_resolution_date: datetime | None = Field(
        default=None, description="Target resolution datetime"
    )
    related_service_id: str | None = Field(
        default=None, description="UUID of the affected Service instance (TMF638)"
    )
    related_ticket_id: str | None = Field(
        default=None, description="UUID of a linked TroubleTicket (TMF621)"
    )


class ServiceProblemPatch(BaseModel):
    """Request body for partial update (PATCH) of a ServiceProblem."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    state: str | None = Field(
        default=None,
        description=(
            "Target state. Valid transitions: submitted→confirmed|rejected, "
            "confirmed→active|rejected, active→resolved, resolved→closed"
        ),
    )
    category: str | None = Field(default=None)
    impact: str | None = Field(default=None)
    priority: int | None = Field(default=None, ge=1, le=4)
    root_cause: str | None = Field(default=None)
    resolution: str | None = Field(default=None)
    expected_resolution_date: datetime | None = Field(default=None)


class ServiceProblemResponse(BaseEntity):
    """Response body for a ServiceProblem."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    state: str
    category: str | None = None
    impact: str | None = None
    priority: int | None = None
    root_cause: str | None = None
    resolution: str | None = None
    expected_resolution_date: datetime | None = None
    resolution_date: datetime | None = None
    related_service_id: str | None = None
    related_ticket_id: str | None = None
    created_at: datetime
    updated_at: datetime
