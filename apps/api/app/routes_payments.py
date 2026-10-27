"""Bank-transfer orders: Ada confirms she has been paid.

In manual mode there is no Paystack webhook to say the money arrived. The buyer sends a receipt, which only
flags the order; Ada checks her own bank account and taps Mark paid in the dashboard. This is the one place a
person, not a signed webhook, marks an order paid, and it only works for bank-transfer orders.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Order, OrderStatus, PaymentMethod
from app.routes import _message_response, _order_response
from app.schemas import MarkPaidResponse
from app.services import flow, payments
from app.services.orders import mark_order_paid

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db)]


@router.post("/orders/{order_id}/mark-paid", response_model=MarkPaidResponse, response_model_exclude_none=True)
def mark_bank_transfer_paid(order_id: str, session: SessionDependency) -> MarkPaidResponse:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    if order.payment_method != PaymentMethod.MANUAL:
        raise HTTPException(status_code=409, detail="This order is paid through Paystack, which confirms it itself")
    if order.status == OrderStatus.PAID:  # a double tap: already done, say so without a second receipt
        return MarkPaidResponse(order=_order_response(session, order))
    if order.status == OrderStatus.EXPIRED and not payments.revive_expired_order(session, order):
        raise HTTPException(
            status_code=409,
            detail="This order expired and its stock has since been sold or released. Contact the buyer.",
        )
    if order.status not in {OrderStatus.PENDING, OrderStatus.EXPIRED}:
        raise HTTPException(status_code=409, detail=f"This order is {order.status.value.lower()}")

    result = mark_order_paid(session, order.paystack_reference or "", order.total_kobo)
    session.commit()
    if "error" in result or not result.get("paid"):
        raise HTTPException(status_code=409, detail="That payment could not be applied")

    message = flow.finish_paid_order(session, order.id)
    session.refresh(order)
    return MarkPaidResponse(
        order=_order_response(session, order), message=_message_response(message) if message else None
    )
