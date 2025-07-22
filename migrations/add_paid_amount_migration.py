"""Add paid_amount column to users table

Revision ID: add_paid_amount
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_paid_amount'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add paid_amount column to users table
    op.add_column('users', sa.Column('paid_amount', sa.Numeric(10, 2), nullable=False, server_default='0'))


def downgrade():
    # Remove paid_amount column from users table
    op.drop_column('users', 'paid_amount') 