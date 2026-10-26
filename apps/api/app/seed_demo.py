from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Conversation, Message, MessageRole, Order, OrderItem, OrderStatus, Product
from app.seed import seed_data


def main() -> None:
    """Create idempotent dashboard-only sample conversations and an order."""
    init_db()
    with SessionLocal() as session:
        seed_data(session)
        product = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
        assert product is not None
        conversation = session.scalar(
            select(Conversation).where(Conversation.customer_phone == "2348000000001")
        )
        if conversation is None:
            conversation = Conversation(
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
            session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price_kobo=4500000,
                )
            )
        session.commit()


if __name__ == "__main__":
    main()
