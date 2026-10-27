from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Conversation, Message, MessageRole, Order, OrderItem, OrderStatus, Product
from app.seed import seed_data


def main() -> None:
    """Create idempotent dashboard-only sample conversations and an order."""
    init_db()
    with SessionLocal() as session:
        vendor = seed_data(session)
        product = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
        brown_product = session.scalar(select(Product).where(Product.sku == "LOAF-BRN-42"))
        assert product is not None
        assert brown_product is not None
        conversation = session.scalar(
            select(Conversation).where(Conversation.customer_phone == "2348000000001")
        )
        if conversation is None:
            conversation = Conversation(
                vendor_id=vendor.id,
                customer_phone="2348000000001",
                customer_name="Funke Adeyemi",
                is_simulator=True,
            )
            session.add(conversation)
            session.flush()
            session.add_all(
                [
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.BUYER,
                        text="Do you have black loafers in size 43?",
                    ),
                    Message(
                        conversation_id=conversation.id,
                        role=MessageRole.AI,
                        text="Yes, we have a pair available.",
                        tool_calls=[
                            {
                                "tool": "search_catalog",
                                "input": {"query": "black loafers size 43"},
                                "output": {
                                    "results": [
                                        {
                                            "productId": product.id,
                                            "sku": product.sku,
                                            "name": product.name,
                                            "priceKobo": product.price_kobo,
                                            "stockOnHand": product.stock,
                                        }
                                    ]
                                },
                            }
                        ],
                    ),
                ]
            )
        second_conversation = session.scalar(
            select(Conversation).where(Conversation.customer_phone == "2348000000002")
        )
        if second_conversation is None:
            second_conversation = Conversation(
                vendor_id=vendor.id,
                customer_phone="2348000000002",
                customer_name="Ibrahim Musa",
            )
            session.add(second_conversation)
            session.flush()
            session.add(
                Message(
                    conversation_id=second_conversation.id,
                    role=MessageRole.BUYER,
                    text="Please send the brown loafers to Yaba.",
                )
            )
        order = session.scalar(select(Order).where(Order.paystack_reference == "SW-DEMO-LOAFERS"))
        if order is None:
            order = Order(
                conversation_id=conversation.id,
                status=OrderStatus.PENDING,
                paystack_reference="SW-DEMO-LOAFERS",
                delivery_fee_kobo=250000,
                total_kobo=4750000,
                delivery_area="Ikeja",
            )
            session.add(order)
            session.flush()
        order_item = session.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
        if order_item is None:
            session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price_kobo=4500000,
                )
            )
        else:
            order_item.product_id = product.id
            order_item.unit_price_kobo = 4500000
        second_order = session.scalar(select(Order).where(Order.paystack_reference == "SW-DEMO-BROWN"))
        if second_order is None:
            second_order = Order(
                conversation_id=second_conversation.id,
                status=OrderStatus.PAID,
                paystack_reference="SW-DEMO-BROWN",
                delivery_fee_kobo=200000,
                total_kobo=4500000,
                delivery_area="Yaba",
            )
            session.add(second_order)
            session.flush()
        second_order_item = session.scalar(select(OrderItem).where(OrderItem.order_id == second_order.id))
        if second_order_item is None:
            session.add(
                OrderItem(
                    order_id=second_order.id,
                    product_id=brown_product.id,
                    quantity=1,
                    unit_price_kobo=4300000,
                )
            )
        else:
            second_order_item.product_id = brown_product.id
            second_order_item.unit_price_kobo = 4300000
        session.commit()


if __name__ == "__main__":
    main()
