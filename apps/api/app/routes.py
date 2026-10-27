from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    Order,
    OrderItem,
    OrderStatus,
    Product,
)
from app.schemas import (
    ConversationEnvelope,
    ConversationResponse,
    ListConversationsResponse,
    ListMessagesResponse,
    ListOrdersResponse,
    ListProductsResponse,
    MessageResponse,
    OrderItemResponse,
    OrderResponse,
    ProductResponse,
    VendorReplyRequest,
    VendorReplyResponse,
)
from app.services.orders import expire_holds
from app.services.whatsapp import send_whatsapp_text

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db)]


def _iso8601(value: datetime | None) -> str:
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _api_status(status: ConversationStatus) -> str:
    return {
        ConversationStatus.ACTIVE: "AI_ACTIVE",
        ConversationStatus.PAUSED: "HUMAN_TAKEOVER",
        ConversationStatus.NEEDS_ATTENTION: "NEEDS_ATTENTION",
    }[status]


def _conversation_response(session: Session, conversation: Conversation) -> ConversationResponse:
    latest_message = session.scalar(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
    )
    return ConversationResponse(
        id=conversation.id,
        customerName=conversation.customer_name or conversation.customer_phone,
        platform="SIMULATOR" if conversation.is_simulator else "WHATSAPP",
        status=_api_status(conversation.status),
        lastMessageAt=_iso8601(latest_message.created_at if latest_message else conversation.created_at),
        preview=latest_message.text if latest_message else "",
    )


def _scrub_tool_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _scrub_tool_value(item) for key, item in value.items() if "floor" not in key.casefold()}
    if isinstance(value, list):
        return [_scrub_tool_value(item) for item in value]
    return value


def _message_response(message: Message) -> MessageResponse:
    tool_calls = None
    if message.role == MessageRole.AI and message.tool_calls:
        tool_calls = [
            {
                "tool": call.get("tool", call.get("name", "")),
                "input": _scrub_tool_value(call.get("input", {})),
                "output": _scrub_tool_value(call.get("output", {})),
            }
            for call in message.tool_calls
            if isinstance(call, dict)
        ]
    return MessageResponse(
        id=message.id,
        conversationId=message.conversation_id,
        sender=message.role.value.upper(),
        body=message.text,
        createdAt=_iso8601(message.created_at),
        toolCalls=tool_calls,
    )


def _not_found(kind: str, identifier: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{kind} {identifier} not found")


@router.get("/conversations", response_model=ListConversationsResponse)
def list_conversations(session: SessionDependency) -> ListConversationsResponse:
    conversations = list(session.scalars(select(Conversation).order_by(Conversation.created_at.desc())))
    rendered = [_conversation_response(session, conversation) for conversation in conversations]
    rendered.sort(key=lambda conversation: conversation.lastMessageAt, reverse=True)
    return ListConversationsResponse(conversations=rendered)


@router.get("/conversations/{conversation_id}/messages", response_model=ListMessagesResponse)
def list_messages(conversation_id: str, session: SessionDependency) -> ListMessagesResponse:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise _not_found("Conversation", conversation_id)
    messages = list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
    )
    return ListMessagesResponse(
        conversation=_conversation_response(session, conversation),
        messages=[_message_response(message) for message in messages],
    )


@router.post("/conversations/{conversation_id}/pause", response_model=ConversationEnvelope)
def pause_conversation(conversation_id: str, session: SessionDependency) -> ConversationEnvelope:
    with session.begin():
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise _not_found("Conversation", conversation_id)
        conversation.ai_paused = True
        conversation.status = ConversationStatus.PAUSED
    return ConversationEnvelope(conversation=_conversation_response(session, conversation))


@router.post("/conversations/{conversation_id}/resume", response_model=ConversationEnvelope)
def resume_conversation(conversation_id: str, session: SessionDependency) -> ConversationEnvelope:
    with session.begin():
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise _not_found("Conversation", conversation_id)
        conversation.ai_paused = False
        conversation.status = ConversationStatus.ACTIVE
    return ConversationEnvelope(conversation=_conversation_response(session, conversation))


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=VendorReplyResponse,
    response_model_exclude_none=True,
)
def send_vendor_reply(
    conversation_id: str, payload: VendorReplyRequest, session: SessionDependency
) -> VendorReplyResponse:
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="body must not be empty")
    with session.begin():
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise _not_found("Conversation", conversation_id)
        conversation.ai_paused = True
        conversation.status = ConversationStatus.PAUSED
        message = Message(conversation_id=conversation.id, role=MessageRole.VENDOR, text=payload.body.strip())
        session.add(message)
        session.flush()
    session.refresh(message)
    if not conversation.is_simulator:
        send_whatsapp_text(conversation.customer_phone, message.text)
    return VendorReplyResponse(
        conversation=_conversation_response(session, conversation), message=_message_response(message)
    )


def _payment_status(status: OrderStatus) -> str:
    if status == OrderStatus.PAID:
        return "PAID"
    if status in {OrderStatus.EXPIRED, OrderStatus.CANCELLED}:
        return "FAILED"
    return "PENDING"


def _order_response(session: Session, order: Order) -> OrderResponse:
    conversation = session.get(Conversation, order.conversation_id)
    order_items = list(session.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
    items = []
    for order_item in order_items:
        product = session.get(Product, order_item.product_id)
        if product is None:
            continue
        items.append(
            OrderItemResponse(
                productId=product.id,
                sku=product.sku,
                name=product.name,
                quantity=order_item.quantity,
                unitPriceKobo=order_item.unit_price_kobo,
            )
        )
    return OrderResponse(
        id=order.id,
        customerName=(conversation.customer_name or conversation.customer_phone) if conversation else "",
        items=items,
        deliveryFeeKobo=order.delivery_fee_kobo,
        totalKobo=order.total_kobo,
        paymentStatus=_payment_status(order.status),
        fulfillmentStatus="PACKAGING" if order.status == OrderStatus.PAID else "UNFULFILLED",
        createdAt=_iso8601(order.created_at or order.expires_at),
        conversationId=order.conversation_id,
        deliveryArea=order.delivery_area,
        paymentReference=order.paystack_reference,
        paymentMethod=order.payment_method.value,
        receiptReportedAt=_iso8601(order.receipt_reported_at) if order.receipt_reported_at else None,
    )


@router.get("/orders", response_model=ListOrdersResponse, response_model_exclude_none=True)
def list_orders(session: SessionDependency) -> ListOrdersResponse:
    expire_holds(session)  # release overdue holds now, since nothing polls for them in the background
    session.commit()
    orders = list(session.scalars(select(Order).order_by(Order.created_at.desc(), Order.id.desc())))
    return ListOrdersResponse(orders=[_order_response(session, order) for order in orders])


@router.get("/products", response_model=ListProductsResponse)
def list_products(session: SessionDependency) -> ListProductsResponse:
    products = list(session.scalars(select(Product).order_by(Product.name.asc())))
    return ListProductsResponse(
        products=[
            ProductResponse(
                id=product.id,
                sku=product.sku,
                name=product.name,
                basePriceKobo=product.price_kobo,
                floorPriceKobo=product.floor_price_kobo,
                stockOnHand=product.stock,
                imageUrl=product.image_url,
            )
            for product in products
        ]
    )
