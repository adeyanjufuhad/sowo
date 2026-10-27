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
    # Bank-transfer orders are confirmed by the vendor, not by Paystack; receiptReportedAt is when the buyer
    # said they had paid.
    paymentMethod: Literal["PAYSTACK", "MANUAL"] | None = None
    receiptReportedAt: str | None = None


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


class SimulatorReceiptRequest(BaseModel):
    reference: str = Field(min_length=1)


class SimulatorReceiptResponse(BaseModel):
    order: OrderResponse
    messages: list[MessageResponse]


class MarkPaidResponse(BaseModel):
    order: OrderResponse
    message: MessageResponse | None = None


class SignupRequest(BaseModel):
    email: str
    password: str
    businessName: str


class LoginRequest(BaseModel):
    email: str
    password: str


class VendorResponse(BaseModel):
    id: str
    name: str
    email: str | None = None


class AuthResponse(BaseModel):
    vendor: VendorResponse
    # Returned once. The web app's server keeps it in an httpOnly cookie and sends it back as a bearer token.
    sessionToken: str
    expiresAt: str


class MeResponse(BaseModel):
    vendor: VendorResponse
