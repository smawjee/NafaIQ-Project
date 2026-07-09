"""Notification preference schemas."""
from __future__ import annotations

from pydantic import BaseModel


class NotifPrefsUpdate(BaseModel):
    email_alerts: bool | None = None
    push_alerts: bool | None = None
    in_app_alerts: bool | None = None
