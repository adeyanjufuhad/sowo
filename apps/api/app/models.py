import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


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


class OfferDecision(str, enum.Enum):
    ACCEPT = "ACCEPT"
    COUNTER = "COUNTER"
    REJECT = "REJECT"
    HANDOFF = "HANDOFF"


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    products: Mapped[list["Product"]] = relationship(back_populates="vendor")
    delivery_zones: Mapped[list["DeliveryZone"]] = relationship(back_populates="vendor")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[str | None] = mapped_column(String(32))
    colour: Mapped[str | None] = mapped_column(String(64))
    price_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    floor_price_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vendor: Mapped[Vendor] = relationship(back_populates="products")


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
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[ConversationStatus] = mapped_column(Enum(ConversationStatus), nullable=False, default=ConversationStatus.ACTIVE)
    ai_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    greeted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_simulator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[OfferDecision] = mapped_column(Enum(OfferDecision), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    paystack_reference: Mapped[str | None] = mapped_column(String(128), unique=True)
    delivery_fee_kobo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
