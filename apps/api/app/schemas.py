from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCallResponse(BaseModel):
    tool: str
    input: dict[str, Any]
    output: dict[str, Any]


class ConversationResponse(BaseModel):
    id: str
    customerName: str
    platform: Literal["WHATSAPP", "SIMULATOR"]
    status: Literal["AI_ACTIVE", "NEEDS_ATTENTION", "HUMAN_TAKEOVER", "CLOSED"]
    lastMessageAt: str
    preview: str


class MessageResponse(BaseModel):
    id: str
    conversationId: str
    sender: Literal["BUYER", "AI", "VENDOR"]
    body: str
    createdAt: str
    toolCalls: list[ToolCallResponse] | None = None


class ListConversationsResponse(BaseModel):
    conversations: list[ConversationResponse]


class ListMessagesResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse]


class ConversationEnvelope(BaseModel):
    conversation: ConversationResponse


class VendorReplyRequest(BaseModel):
    body: str = Field(min_length=1)


class VendorReplyResponse(BaseModel):
    conversation: ConversationResponse
    message: MessageResponse


class OrderItemResponse(BaseModel):
    productId: str
    sku: str
    name: str
    quantity: int
    unitPriceKobo: int


class OrderResponse(BaseModel):
    id: str
    customerName: str
    items: list[OrderItemResponse]
    deliveryFeeKobo: int
    totalKobo: int
    paymentStatus: Literal["PENDING", "PAID", "FAILED", "REFUNDED"]
    fulfillmentStatus: Literal["UNFULFILLED", "PACKAGING", "SHIPPED", "DELIVERED"]
    createdAt: str
    conversationId: str | None = None
    deliveryArea: str | None = None
    paymentReference: str | None = None


class ListOrdersResponse(BaseModel):
    orders: list[OrderResponse]


class ProductResponse(BaseModel):
    id: str
    sku: str
    name: str
    basePriceKobo: int
    floorPriceKobo: int
    stockOnHand: int
    imageUrl: str


class ListProductsResponse(BaseModel):
    products: list[ProductResponse]


class SimulatorMessageRequest(BaseModel):
    conversationId: str | None = None
    customerName: str | None = None
    body: str = Field(min_length=1)


class SimulatorMessageResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse]


class SimulatorPaymentRequest(BaseModel):
    reference: str = Field(min_length=1)
    outcome: Literal["SUCCESS", "FAILED"]


class SimulatorPaymentResponse(BaseModel):
    order: OrderResponse
    messages: list[MessageResponse]
