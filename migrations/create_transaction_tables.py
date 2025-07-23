"""Create transaction and transaction_details tables

Revision ID: create_transaction_tables
Revises: add_paid_amount
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_transaction_tables'
down_revision = 'add_paid_amount'
branch_labels = None
depends_on = None


def upgrade():
    # Create transactions table
    op.create_table('transactions',
        sa.Column('id', sa.String(20), nullable=False),
        sa.Column('total_reference_count', sa.Integer(), nullable=False),
        sa.Column('total_reference_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reference_code', sa.String(50), nullable=False),
        sa.Column('discount_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('received_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create transaction_details table
    op.create_table('transaction_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop transaction_details table first (due to foreign key constraint)
    op.drop_table('transaction_details')
    # Drop transactions table
    op.drop_table('transactions') 