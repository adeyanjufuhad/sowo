import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    PAUSED = "PAUSED"


class MessageRole(str, enum.Enum):
    BUYER = "buyer"
    AI = "ai"
    VENDOR = "vendor"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, enum.Enum):
    PAYSTACK = "PAYSTACK"
    MANUAL = "MANUAL"


class OfferDecision(str, enum.Enum):
    ACCEPT = "ACCEPT"
    COUNTER = "COUNTER"
    REJECT = "REJECT"
    HANDOFF = "HANDOFF"


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # Login. Both stay empty for a vendor created before accounts existed (or by the demo seed) until they are claimed.
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    # What buyers call the person behind the shop ("Ada"). Falls back to the business name when empty.
    owner_name: Mapped[str | None] = mapped_column(String(80))
    # The vendor's WhatsApp business number, as Meta's Cloud API names it. It is how an incoming message finds its
    # vendor, and which number replies are sent from.
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    # Where "pack this" and "needs you" alerts go (the vendor's own phone).
    alert_phone: Mapped[str | None] = mapped_column(String(32))
    # "paystack": a Paystack link, confirmed by Paystack's signed webhook. "manual": a bank transfer to the account
    # below, confirmed by the vendor in the dashboard once the money shows up.
    payment_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="paystack", server_default="paystack")
    bank_name: Mapped[str | None] = mapped_column(String(80))
    bank_account_name: Mapped[str | None] = mapped_column(String(120))
    bank_account_number: Mapped[str | None] = mapped_column(String(10))
    # The SIMULATOR_VENDOR_NAME that first picked this shop for the /try demo. Remembering it means the shop can
    # rename itself without the demo losing it, and nobody else can take the demo over by signing up as the old name.
    simulator_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    products: Mapped[list["Product"]] = relationship(back_populates="vendor")
    delivery_zones: Mapped[list["DeliveryZone"]] = relationship(back_populates="vendor")


class VendorSession(Base):
    """A signed-in dashboard session. Only a hash of the token is stored, so a database leak can't be replayed."""

    __tablename__ = "vendor_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("vendor_id", "sku", name="uq_products_vendor_id_sku"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[str | None] = mapped_column(String(32))
    colour: Mapped[str | None] = mapped_column(String(64))
    # The vendor's own grouping ("Shoes", "Bags"). The assistant searches it, so "which shoes do you have?" works.
    category: Mapped[str | None] = mapped_column(String(64))
    price_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    floor_price_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Set when the vendor removes a product that has already been ordered or haggled over: it stops being sold or
    # shown, but the orders that mention it keep working.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vendor: Mapped[Vendor] = relationship(back_populates="products")


class ProductImage(Base):
    """A picture a vendor uploaded for a product. It lives in the database because the free hosts this runs on lose
    their disk on every deploy; the web app resizes it before sending, so a row stays small. The product points at it
    with image_url = "/product-images/<id>"."""

    __tablename__ = "product_images"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())


class DeliveryZone(Base):
    __tablename__ = "delivery_zones"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    area: Mapped[str] = mapped_column(String(100), nullable=False)
    fee_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    vendor: Mapped[Vendor] = relationship(back_populates="delivery_zones")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    status: Mapped[ConversationStatus] = mapped_column(Enum(ConversationStatus), nullable=False, default=ConversationStatus.ACTIVE)
    ai_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    greeted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_simulator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


def new_quote_id() -> str:
    return f"q_{uuid.uuid4().hex[:8]}"


class Quote(Base):
    """A priced basket the buyer was shown. request_payment turns one into an order."""

    __tablename__ = "quotes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_quote_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    items: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    delivery_area: Mapped[str] = mapped_column(String(100), nullable=False)
    total_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[OfferDecision] = mapped_column(Enum(OfferDecision), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    paystack_reference: Mapped[str | None] = mapped_column(String(128), unique=True)
    delivery_fee_kobo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_area: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # MANUAL orders are paid by bank transfer and confirmed by the vendor, not by a Paystack webhook.
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), nullable=False, default=PaymentMethod.PAYSTACK, server_default=PaymentMethod.PAYSTACK.name
    )
    receipt_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    order: Mapped[Order] = relationship(back_populates="items")


class StockHold(Base):
    __tablename__ = "stock_holds"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
