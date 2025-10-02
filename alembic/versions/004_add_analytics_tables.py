"""Add analytics tables

Revision ID: 004
Revises: 003
Create Date: 2025-10-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create analytics_metrics table
    op.create_table(
        'analytics_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('metric_type', sa.String(length=100), nullable=False),
        sa.Column('granularity', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('count', sa.Integer(), nullable=True),
        sa.Column('metric_metadata', sa.JSON(), nullable=True),
        sa.Column('min_value', sa.Float(), nullable=True),
        sa.Column('max_value', sa.Float(), nullable=True),
        sa.Column('avg_value', sa.Float(), nullable=True),
        sa.Column('sum_value', sa.Float(), nullable=True),
        sa.Column('breakdown', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for analytics_metrics
    op.create_index('ix_analytics_metrics_organization_id', 'analytics_metrics', ['organization_id'])
    op.create_index('ix_analytics_metrics_metric_type', 'analytics_metrics', ['metric_type'])
    op.create_index('ix_analytics_metrics_granularity', 'analytics_metrics', ['granularity'])
    op.create_index('ix_analytics_metrics_timestamp', 'analytics_metrics', ['timestamp'])
    op.create_index(
        'ix_analytics_metrics_org_metric_time',
        'analytics_metrics',
        ['organization_id', 'metric_type', 'timestamp']
    )

    # Create analytics_snapshots table
    op.create_table(
        'analytics_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_type', sa.String(length=100), nullable=False),
        sa.Column('snapshot_date', sa.DateTime(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.Column('is_complete', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for analytics_snapshots
    op.create_index('ix_analytics_snapshots_organization_id', 'analytics_snapshots', ['organization_id'])
    op.create_index('ix_analytics_snapshots_snapshot_date', 'analytics_snapshots', ['snapshot_date'])
    op.create_index(
        'ix_analytics_snapshots_org_type_date',
        'analytics_snapshots',
        ['organization_id', 'snapshot_type', 'snapshot_date']
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_analytics_snapshots_org_type_date', table_name='analytics_snapshots')
    op.drop_index('ix_analytics_snapshots_snapshot_date', table_name='analytics_snapshots')
    op.drop_index('ix_analytics_snapshots_organization_id', table_name='analytics_snapshots')

    op.drop_index('ix_analytics_metrics_org_metric_time', table_name='analytics_metrics')
    op.drop_index('ix_analytics_metrics_timestamp', table_name='analytics_metrics')
    op.drop_index('ix_analytics_metrics_granularity', table_name='analytics_metrics')
    op.drop_index('ix_analytics_metrics_metric_type', table_name='analytics_metrics')
    op.drop_index('ix_analytics_metrics_organization_id', table_name='analytics_metrics')

    # Drop tables
    op.drop_table('analytics_snapshots')
    op.drop_table('analytics_metrics')
