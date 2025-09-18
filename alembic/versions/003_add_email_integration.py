"""Add email integration tables

Revision ID: 003_add_email_integration
Revises: 002_add_ml_fields
Create Date: 2025-09-08 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '003_add_email_integration'
down_revision = '002_add_ml_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Create email_integrations table
    op.create_table('email_integrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password', sa.Text(), nullable=False),
        sa.Column('server', sa.String(length=255), nullable=True),
        sa.Column('port', sa.Integer(), nullable=False, default=993),
        sa.Column('ssl', sa.Boolean(), nullable=False, default=True),
        sa.Column('mailboxes', sa.JSON(), nullable=False),
        sa.Column('sync_frequency', sa.Integer(), nullable=False, default=300),
        sa.Column('auto_create_tickets', sa.Boolean(), nullable=False, default=True),
        sa.Column('auto_reply', sa.Boolean(), nullable=False, default=False),
        sa.Column('batch_size', sa.Integer(), nullable=False, default=50),
        sa.Column('days_back', sa.Integer(), nullable=False, default=7),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('total_emails_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('total_tickets_created', sa.Integer(), nullable=False, default=0),
        sa.Column('total_duplicates_filtered', sa.Integer(), nullable=False, default=0),
        sa.Column('avg_processing_time', sa.Float(), nullable=False, default=0.0),
        sa.Column('auto_reply_template', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_email_integrations_organization_id'), 'email_integrations', ['organization_id'], unique=False)
    
    # Create email_processing_logs table
    op.create_table('email_processing_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('integration_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('emails_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('emails_new', sa.Integer(), nullable=False, default=0),
        sa.Column('emails_duplicate', sa.Integer(), nullable=False, default=0),
        sa.Column('tickets_created', sa.Integer(), nullable=False, default=0),
        sa.Column('processing_time', sa.Float(), nullable=False, default=0.0),
        sa.Column('mailbox_results', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['integration_id'], ['email_integrations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_email_processing_logs_integration_id'), 'email_processing_logs', ['integration_id'], unique=False)


def downgrade():
    # Drop tables and indexes
    op.drop_index(op.f('ix_email_processing_logs_integration_id'), table_name='email_processing_logs')
    op.drop_table('email_processing_logs')
    op.drop_index(op.f('ix_email_integrations_organization_id'), table_name='email_integrations')
    op.drop_table('email_integrations')