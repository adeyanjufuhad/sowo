from typing import Any, Literal

from pydantic import BaseModel, Field, StrictInt


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
    description: str = ""
    size: str | None = None
    colour: str | None = None
    category: str | None = None


class ListProductsResponse(BaseModel):
    products: list[ProductResponse]


class SimulatorMessageRequest(BaseModel):
    conversationId: str | None = None
    customerName: str | None = None
    body: str = Field(min_length=1)


class SimulatorMessageResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse]


class SimulatorShopResponse(BaseModel):
    """Who the /try buyer is talking to. Only what any buyer would see on WhatsApp."""

    businessName: str
    ownerName: str  # falls back to the business name, the same way the assistant names the owner


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


class VendorSettingsResponse(BaseModel):
    """The shop's own setup. Bank details are the vendor's to see; nothing here ever reaches the model."""

    businessName: str
    ownerName: str | None = None
    whatsappPhoneNumberId: str | None = None
    alertPhone: str | None = None
    paymentMode: Literal["paystack", "manual"]
    bankName: str | None = None
    bankAccountName: str | None = None
    bankAccountNumber: str | None = None
    # Can the shop take an order with the payment mode it has chosen? (Bank transfer needs complete bank details.)
    paymentReady: bool
    # Can Sowo answer buyers who message this shop's WhatsApp number?
    whatsappConnected: bool


class VendorSettingsUpdate(BaseModel):
    """Send only what changes. null (or an empty string) clears an optional setting; businessName can't be cleared."""

    businessName: str | None = None
    ownerName: str | None = None
    whatsappPhoneNumberId: str | None = None
    alertPhone: str | None = None
    paymentMode: Literal["paystack", "manual"] | None = None
    bankName: str | None = None
    bankAccountName: str | None = None
    bankAccountNumber: str | None = None


class ProductCreate(BaseModel):
    """A new product. Prices are whole kobo; the floor price is the lowest the vendor will accept and stays private."""

    sku: str
    name: str
    description: str = ""
    size: str | None = None
    colour: str | None = None
    category: str | None = None
    basePriceKobo: StrictInt
    floorPriceKobo: StrictInt
    stockOnHand: StrictInt = 0
    imageUrl: str = ""


class ProductUpdate(BaseModel):
    """Send only what changes. size, colour and category accept null to clear them."""

    sku: str | None = None
    name: str | None = None
    description: str | None = None
    size: str | None = None
    colour: str | None = None
    category: str | None = None
    basePriceKobo: StrictInt | None = None
    floorPriceKobo: StrictInt | None = None
    stockOnHand: StrictInt | None = None
    imageUrl: str | None = None


class ProductEnvelope(BaseModel):
    product: ProductResponse


class ProductImageUpload(BaseModel):
    """A picture for a product, base64 encoded (the web app has already shrunk it)."""

    data: str


class ProductImageResponse(BaseModel):
    imageUrl: str  # put this in a product's imageUrl


class DeleteProductResponse(BaseModel):
    deleted: bool  # gone for good
    archived: bool  # kept for the orders that mention it, but no longer sold or shown


class DeliveryZoneResponse(BaseModel):
    id: str
    area: str
    feeKobo: int


class DeliveryZoneCreate(BaseModel):
    area: str
    feeKobo: StrictInt


class DeliveryZoneUpdate(BaseModel):
    area: str | None = None
    feeKobo: StrictInt | None = None


class ListDeliveryZonesResponse(BaseModel):
    zones: list[DeliveryZoneResponse]


class DeliveryZoneEnvelope(BaseModel):
    zone: DeliveryZoneResponse

