"""Initial schema: everything the API had before accounts, multi-vendor routing and catalog management.

Revision ID: 0001
Revises: 
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table('conversations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('customer_phone', sa.String(length=32), nullable=False),
    sa.Column('customer_name', sa.String(length=120), nullable=False),
    sa.Column('status', sa.Enum('ACTIVE', 'NEEDS_ATTENTION', 'PAUSED', name='conversationstatus'), nullable=False),
    sa.Column('ai_paused', sa.Boolean(), nullable=False),
    sa.Column('greeted', sa.Boolean(), nullable=False),
    sa.Column('is_simulator', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_customer_phone', 'conversations', ['customer_phone'], unique=False)

    op.create_table('vendors',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('delivery_zones',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('vendor_id', sa.String(length=36), nullable=False),
    sa.Column('area', sa.String(length=100), nullable=False),
    sa.Column('fee_kobo', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_delivery_zones_vendor_id', 'delivery_zones', ['vendor_id'], unique=False)

    op.create_table('messages',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('conversation_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.Enum('BUYER', 'AI', 'VENDOR', name='messagerole'), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('tool_calls', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('whatsapp_message_id', sa.String(length=128), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('whatsapp_message_id')
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'], unique=False)

    op.create_table('orders',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('conversation_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'PAID', 'EXPIRED', 'CANCELLED', name='orderstatus'), nullable=False),
    sa.Column('paystack_reference', sa.String(length=128), nullable=True),
    sa.Column('delivery_fee_kobo', sa.Integer(), nullable=False),
    sa.Column('total_kobo', sa.Integer(), nullable=False),
    sa.Column('delivery_area', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('payment_method', sa.Enum('PAYSTACK', 'MANUAL', name='paymentmethod'), server_default='PAYSTACK', nullable=False),
    sa.Column('receipt_reported_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('paystack_reference')
    )
    op.create_index('ix_orders_conversation_id', 'orders', ['conversation_id'], unique=False)

    op.create_table('products',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('vendor_id', sa.String(length=36), nullable=False),
    sa.Column('sku', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('size', sa.String(length=32), nullable=True),
    sa.Column('colour', sa.String(length=64), nullable=True),
    sa.Column('price_kobo', sa.Integer(), nullable=False),
    sa.Column('floor_price_kobo', sa.Integer(), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=False),
    sa.Column('image_url', sa.String(length=500), nullable=False),
    sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sku')
    )
    op.create_index('ix_products_vendor_id', 'products', ['vendor_id'], unique=False)

    op.create_table('quotes',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('conversation_id', sa.String(length=36), nullable=False),
    sa.Column('items', sa.JSON(), nullable=False),
    sa.Column('delivery_area', sa.String(length=100), nullable=False),
    sa.Column('total_kobo', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_quotes_conversation_id', 'quotes', ['conversation_id'], unique=False)

    op.create_table('offers',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('conversation_id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('amount_kobo', sa.Integer(), nullable=False),
    sa.Column('decision', sa.Enum('ACCEPT', 'COUNTER', 'REJECT', 'HANDOFF', name='offerdecision'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_offers_conversation_id', 'offers', ['conversation_id'], unique=False)

    op.create_table('order_items',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('order_id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price_kobo', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'], unique=False)

    op.create_table('stock_holds',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('order_id', sa.String(length=36), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_stock_holds_order_id', 'stock_holds', ['order_id'], unique=False)
    op.create_index('ix_stock_holds_product_id', 'stock_holds', ['product_id'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_stock_holds_product_id', table_name='stock_holds')
    op.drop_index('ix_stock_holds_order_id', table_name='stock_holds')

    op.drop_table('stock_holds')
    op.drop_index('ix_order_items_order_id', table_name='order_items')

    op.drop_table('order_items')
    op.drop_index('ix_offers_conversation_id', table_name='offers')

    op.drop_table('offers')
    op.drop_index('ix_quotes_conversation_id', table_name='quotes')

    op.drop_table('quotes')
    op.drop_index('ix_products_vendor_id', table_name='products')

    op.drop_table('products')
    op.drop_index('ix_orders_conversation_id', table_name='orders')

    op.drop_table('orders')
    op.drop_index('ix_messages_conversation_id', table_name='messages')

    op.drop_table('messages')
    op.drop_index('ix_delivery_zones_vendor_id', table_name='delivery_zones')

    op.drop_table('delivery_zones')
    op.drop_table('vendors')
    op.drop_index('ix_conversations_customer_phone', table_name='conversations')

    op.drop_table('conversations')
    bind = op.get_bind()
    for name in ("conversationstatus", "messagerole", "orderstatus", "paymentmethod", "offerdecision"):
        sa.Enum(name=name).drop(bind, checkfirst=True)
