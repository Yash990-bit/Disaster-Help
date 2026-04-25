"""
Pydantic models for the Smart City Emergency Dispatch System.
Defines the IncidentReport schema used by Agent 1 and shared memory.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ─── Allowed Resource Types ──────────────────────────────────────────────────
ALLOWED_RESOURCES = [
    "ambulance",
    "fire_truck",
    "police",
    "utilities_gas",
    "utilities_power",
    "utilities_water",
    "hazmat",
]

# ─── Department Mapping (auto-derive from resources) ─────────────────────────
RESOURCE_TO_DEPARTMENT = {
    "ambulance": "ambulance_service",
    "fire_truck": "fire_dept",
    "police": "police_dept",
    "utilities_gas": "utilities_team",
    "utilities_power": "utilities_team",
    "utilities_water": "utilities_team",
    "hazmat": "hazmat_team",
}


def derive_departments(resources: list[str]) -> list[str]:
    """
    Given a list of required_resources, return deduplicated
    list of departments to notify using RESOURCE_TO_DEPARTMENT mapping.
    """
    departments = set()
    for resource in resources:
        dept = RESOURCE_TO_DEPARTMENT.get(resource)
        if dept:
            departments.add(dept)
    return sorted(departments)


# ─── IncidentReport Model ───────────────────────────────────────────────────
class IncidentReport(BaseModel):
    """Structured incident report produced by Agent 1."""

    incident_id: str = Field(
        ...,
        description="Unique incident ID in format INC-YYYYMMDD-XXX"
    )
    location: str = Field(
        ...,
        description="Best estimate of address or landmark"
    )
    severity: int = Field(
        ...,
        ge=1,
        le=5,
        description="Severity scale: 1=Minor, 2=Moderate, 3=Serious, 4=Critical, 5=Catastrophic"
    )
    required_resources: list[str] = Field(
        default_factory=list,
        description="Resources needed from ALLOWED_RESOURCES list"
    )
    departments_to_notify: list[str] = Field(
        default_factory=list,
        description="Auto-derived from required_resources via RESOURCE_TO_DEPARTMENT mapping"
    )
    caller_count: int = Field(
        default=1,
        ge=1,
        description="Number of 911 calls merged into this incident"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in location and severity accuracy (0.0–1.0)"
    )
    status: str = Field(
        default="active",
        description="Incident status: active / processing / dispatched / resolved"
    )
    claimed_by: Optional[str] = Field(
        default=None,
        description="Agent 2 claims this incident for dispatch (null initially)"
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 UTC timestamp of incident creation"
    )
    raw_transcripts: list[str] = Field(
        default_factory=list,
        description="All original 911 call transcripts merged into this incident"
    )
    embedding: list[float] = Field(
        default_factory=list,
        description="Vector embedding of the incident (stored but not shown in UI)"
    )
    resource_gaps: list[str] = Field(
        default_factory=list,
        description="Resources still needed but not yet dispatched (empty initially)"
    )
    escalated: bool = Field(
        default=False,
        description="Whether this incident has been escalated from original severity"
    )
