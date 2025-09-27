"""Initial migration - create all tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("timezone", sa.String(length=50), nullable=False),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("plan", sa.String(length=50), nullable=False),
        sa.Column("max_users", sa.Integer(), nullable=False),
        sa.Column("max_tickets_per_month", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)
    op.create_index(
        op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True
    )

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column(
            "role", sa.Enum("ADMIN", "USER", "VIEWER", name="userrole"), nullable=False
        ),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("timezone", sa.String(length=50), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("email_notifications", sa.Boolean(), nullable=False),
        sa.Column("slack_notifications", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    # Create integrations table
    op.create_table(
        "integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "SLACK", "ZENDESK", "EMAIL", "DISCORD", "TEAMS", name="integrationtype"
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "INACTIVE", "ERROR", "PENDING", name="integrationstatus"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("webhook_url", sa.String(length=512), nullable=True),
        sa.Column("webhook_secret", sa.String(length=255), nullable=True),
        sa.Column("api_endpoint", sa.String(length=512), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sync_frequency", sa.Integer(), nullable=False),
        sa.Column("sync_tickets", sa.Boolean(), nullable=False),
        sa.Column("receive_webhooks", sa.Boolean(), nullable=False),
        sa.Column("send_notifications", sa.Boolean(), nullable=False),
        sa.Column("rate_limit_per_hour", sa.Integer(), nullable=False),
        sa.Column("current_hour_requests", sa.Integer(), nullable=False),
        sa.Column("rate_limit_reset_at", sa.DateTime(), nullable=True),
        sa.Column("total_tickets_synced", sa.Integer(), nullable=False),
        sa.Column("total_webhooks_received", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integrations_id"), "integrations", ["id"], unique=False)

    # Create tickets table
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "IN_PROGRESS",
                "RESOLVED",
                "CLOSED",
                "PENDING",
                name="ticketstatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("LOW", "MEDIUM", "HIGH", "URGENT", name="ticketpriority"),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.Enum("EMAIL", "SLACK", "ZENDESK", "API", "WEB", name="ticketchannel"),
            nullable=False,
        ),
        sa.Column("customer_email", sa.String(length=255), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=50), nullable=True),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=True),
        sa.Column("first_response_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("urgency_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("ticket_metadata", sa.JSON(), nullable=True),
        sa.Column("is_processed", sa.Boolean(), nullable=False),
        sa.Column("needs_human_review", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tickets_customer_email"), "tickets", ["customer_email"], unique=False
    )
    op.create_index(
        op.f("ix_tickets_external_id"), "tickets", ["external_id"], unique=False
    )
    op.create_index(op.f("ix_tickets_id"), "tickets", ["id"], unique=False)


def downgrade() -> None:
    op.drop_table("tickets")
    op.drop_table("integrations")
    op.drop_table("users")
    op.drop_table("organizations")
