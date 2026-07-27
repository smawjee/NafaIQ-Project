"""Admin dashboard request/response DTOs. Typed — no bare dicts on the wire."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

VALID_PLANS = ("Free", "Pro", "Premium")
VALID_STATUSES = ("active", "suspended", "restricted")


# --- Common -----------------------------------------------------------------
class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


# --- Identity ---------------------------------------------------------------
class AdminMe(BaseModel):
    user_id: str
    email: str
    roles: list[str]
    permissions: list[str]


# --- Users ------------------------------------------------------------------
class UserListItem(BaseModel):
    id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    plan: str
    account_status: str
    created_at: Optional[datetime] = None
    last_sign_in_at: Optional[datetime] = None


class UserActivity(BaseModel):
    """Per-user counts. None on any field means the metric is currently
    unavailable (query failed) — never a fabricated zero."""
    available: bool
    counts: dict[str, int] = Field(default_factory=dict)


class AdminNote(BaseModel):
    id: int
    author_id: Optional[str] = None
    note: str
    created_at: datetime


class RoleAssignmentInfo(BaseModel):
    id: int
    role_slug: str
    granted_by: Optional[str] = None
    granted_at: datetime
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    reason: Optional[str] = None


class UserDetail(BaseModel):
    id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    plan: str
    account_status: str
    status_reason: Optional[str] = None
    status_changed_at: Optional[datetime] = None
    plan_selected_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    last_sign_in_at: Optional[datetime] = None
    email_confirmed_at: Optional[datetime] = None
    activity: UserActivity
    roles: list[str] = Field(default_factory=list)
    notes: list[AdminNote] = Field(default_factory=list)


class StatusChangeRequest(BaseModel):
    status: str = Field(..., pattern="^(active|suspended|restricted)$")
    reason: Optional[str] = Field(None, max_length=500)


class TierChangeRequest(BaseModel):
    plan: str = Field(..., pattern="^(Free|Pro|Premium)$")
    reason: Optional[str] = Field(None, max_length=500)


class NoteCreate(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)


# --- Roles ------------------------------------------------------------------
class RoleInfo(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    permissions: list[str] = Field(default_factory=list)


class PermissionInfo(BaseModel):
    slug: str
    description: Optional[str] = None


class AdminListItem(BaseModel):
    user_id: str
    email: Optional[str] = None
    roles: list[str]
    first_granted_at: Optional[datetime] = None


class RoleGrantRequest(BaseModel):
    role_slug: str = Field(..., min_length=1, max_length=50)
    reason: Optional[str] = Field(None, max_length=500)


# --- Flags ------------------------------------------------------------------
class FlagInfo(BaseModel):
    key: str
    type: str
    value: Any
    allowed: Optional[Any] = None
    enabled: bool
    description: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class FlagUpdate(BaseModel):
    value: Any
    enabled: Optional[bool] = None
    reason: Optional[str] = Field(None, max_length=500)


# --- Audit ------------------------------------------------------------------
class AuditEntry(BaseModel):
    id: int
    actor_user_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_roles: list[str] = Field(default_factory=list)
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    target_user_id: Optional[str] = None
    before: Optional[Any] = None
    after: Optional[Any] = None
    reason: Optional[str] = None
    request_id: Optional[str] = None
    ip: Optional[str] = None
    status: str
    created_at: datetime


# --- Overview ---------------------------------------------------------------
class MetricBlock(BaseModel):
    """A group of metrics that is either available (real numbers) or not."""
    available: bool
    data: dict[str, Any] = Field(default_factory=dict)


class OverviewResponse(BaseModel):
    users: MetricBlock
    tiers: MetricBlock
    engagement: MetricBlock
    recent_actions: list[AuditEntry]
