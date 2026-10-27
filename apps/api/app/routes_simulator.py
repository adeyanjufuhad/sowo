"""The buyer simulator behind the web app's /try page: the same agent as WhatsApp, without WhatsApp.

Simulator chats are flagged (is_simulator) and never send anything to WhatsApp. The payment endpoint stands
in for Paystack's webhook, and it can only touch simulator orders, never a real buyer's.
"""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import ChatModelDependency
from app.models import Conversation, MessageRole, Order, OrderStatus, PaymentMethod
from app.routes import _conversation_response, _message_response, _order_response
from app.schemas import (
    SimulatorMessageRequest,
    SimulatorMessageResponse,
    SimulatorPaymentRequest,
    SimulatorPaymentResponse,
    SimulatorReceiptRequest,
    SimulatorReceiptResponse,
)
from app.services import flow, payments
from app.services.orders import mark_order_paid

SessionDependency = Annotated[Session, Depends(get_db)]


def _require_simulator() -> None:
    if not get_settings().simulator_enabled:
        raise HTTPException(status_code=404, detail="The simulator is turned off")


router = APIRouter(dependencies=[Depends(_require_simulator)])


@router.post("/simulator/messages", response_model=SimulatorMessageResponse, response_model_exclude_none=True)
def send_simulator_message(
    payload: SimulatorMessageRequest, session: SessionDependency, model: ChatModelDependency
) -> SimulatorMessageResponse:
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="body must not be empty")
    if payload.conversationId:
        conversation = session.get(Conversation, payload.conversationId)
        if conversation is None or not conversation.is_simulator:
            raise HTTPException(status_code=404, detail=f"Conversation {payload.conversationId} not found")
    else:
        conversation = Conversation(
            customer_phone=f"sim-{uuid4().hex[:10]}",
            customer_name=(payload.customerName or "Demo buyer").strip()[:120] or "Demo buyer",
            is_simulator=True,
        )
        session.add(conversation)
        session.commit()

    messages = [flow.add_message(session, conversation, MessageRole.BUYER, body)]
    reply = flow.answer_buyer(session, conversation, model, get_settings(), deliver=False)
    if reply is not None:
        messages.append(reply)
    return SimulatorMessageResponse(
        conversation=_conversation_response(session, conversation),
        messages=[_message_response(message) for message in messages],
    )


@router.post("/simulator/payments", response_model=SimulatorPaymentResponse, response_model_exclude_none=True)
def simulate_payment(payload: SimulatorPaymentRequest, session: SessionDependency) -> SimulatorPaymentResponse:
    order = session.scalar(select(Order).where(Order.paystack_reference == payload.reference))
    conversation = session.get(Conversation, order.conversation_id) if order else None
    if order is None or conversation is None or not conversation.is_simulator:
        raise HTTPException(status_code=404, detail=f"Payment {payload.reference} not found")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Order is already {order.status.value}")
    if order.payment_method == PaymentMethod.MANUAL:
        raise HTTPException(status_code=409, detail="Bank-transfer orders are confirmed by Ada in the dashboard")

    if payload.outcome == "SUCCESS":
        result = mark_order_paid(session, payload.reference, order.total_kobo)
        session.commit()
        if "error" in result or not result.get("paid"):
            raise HTTPException(status_code=409, detail="That payment could not be applied")
        message = flow.finish_paid_order(session, order.id)
    else:
        payments.release_order(session, order.id)
        session.commit()
        message = flow.finish_failed_order(session, order.id)

    session.refresh(order)
    return SimulatorPaymentResponse(
        order=_order_response(session, order),
        messages=[_message_response(message)] if message else [],
    )


@router.post("/simulator/receipts", response_model=SimulatorReceiptResponse, response_model_exclude_none=True)
def send_simulated_receipt(payload: SimulatorReceiptRequest, session: SessionDependency) -> SimulatorReceiptResponse:
    """The buyer says they've made the bank transfer. Ada still has to confirm it in the dashboard."""
    order = session.scalar(select(Order).where(Order.paystack_reference == payload.reference))
    conversation = session.get(Conversation, order.conversation_id) if order else None
    if order is None or conversation is None or not conversation.is_simulator:
        raise HTTPException(status_code=404, detail=f"Order {payload.reference} not found")
    if order.payment_method != PaymentMethod.MANUAL or order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=409, detail="That order is not waiting for a bank transfer")

    messages = flow.submit_simulated_receipt(session, conversation, order, get_settings())
    session.refresh(order)
    return SimulatorReceiptResponse(
        order=_order_response(session, order), messages=[_message_response(m) for m in messages]
    )
