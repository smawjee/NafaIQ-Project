"""User-scoped alerts API: CRUD, events, evaluation (thin HTTP layer)."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_user
from app.schemas.alerts import AppAlertCreate, AppAlertToggle, PriceAlertCreate
from app.services import alerts as alerts_service

router = APIRouter(tags=["alerts"])


# ---------- CRUD for app-level alerts (bill / budget / goal) ----------


@router.get("/alerts")
async def list_alerts(
    user: Annotated[dict, Depends(require_user)],
    type: Optional[str] = None,
):
    return await alerts_service.list_alerts(user["user_id"], alert_type=type)


@router.post("/alerts")
async def create_alert(
    body: AppAlertCreate,
    user: Annotated[dict, Depends(require_user)],
):
    return await alerts_service.create_user_alert(
        user["user_id"],
        alert_type=body.type,
        title=body.title,
        meta=body.meta or {},
        enabled=body.enabled,
    )


@router.patch("/alerts/{alert_id}")
async def toggle_alert(
    alert_id: int,
    body: AppAlertToggle,
    user: Annotated[dict, Depends(require_user)],
):
    result = await alerts_service.toggle_alert(
        user["user_id"], alert_id, body.enabled
    )
    if not result:
        raise HTTPException(404, "Alert not found")
    return result


@router.delete("/alerts/{alert_id}")
async def delete_alert(
    alert_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    ok = await alerts_service.delete_alert(user["user_id"], alert_id)
    if not ok:
        raise HTTPException(404, "Alert not found")
    return {"deleted": alert_id}


# ---------- Price alerts ----------


@router.get("/alerts/price")
async def list_price_alerts(user: Annotated[dict, Depends(require_user)]):
    return await alerts_service.list_alerts(user["user_id"], alert_type="price")


@router.post("/alerts/price")
async def create_price_alert(
    body: PriceAlertCreate,
    user: Annotated[dict, Depends(require_user)],
):
    return await alerts_service.create_price_alert(
        user,
        symbol=body.symbol,
        condition=body.condition,
        price=body.price,
        one_time=body.one_time,
        notify_push=body.notify_push,
        notify_email=body.notify_email,
        notes=body.notes,
    )


# ---------- Events (notification history) ----------


@router.get("/alerts/events")
async def list_events(
    user: Annotated[dict, Depends(require_user)],
    limit: int = 50,
):
    return await alerts_service.list_alert_events(user["user_id"], limit=limit)


@router.patch("/alerts/events/{event_id}/read")
async def mark_event_read(
    event_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    ok = await alerts_service.mark_event_read(user["user_id"], event_id)
    if not ok:
        raise HTTPException(404, "Event not found")
    return {"id": event_id, "read_at_set": True}


# ---------- Manual evaluate (test trigger) ----------


@router.post("/alerts/evaluate")
async def evaluate(user: Annotated[dict, Depends(require_user)]):
    """Trigger all evaluators. Returns count of new events created."""
    return await alerts_service.evaluate_all()
