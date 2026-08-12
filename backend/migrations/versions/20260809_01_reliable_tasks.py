"""Add reliable signing activities, tasks, refresh tokens, and outbox."""
from alembic import op
from alembic import context
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260809_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    inspector = None if context.is_offline_mode() else inspect(op.get_bind())
    tables = set() if inspector is None else set(inspector.get_table_names())
    if "users" not in tables:
        op.create_table("users",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("nickname", sa.String(64), nullable=False),
            sa.Column("phone", sa.String(20), nullable=False, unique=True), sa.Column("password_hash", sa.String(256)),
            sa.Column("cookie_manual", sa.Text()), sa.Column("cookie_expire_at", sa.DateTime()),
            sa.Column("cookie_source", sa.String(10), server_default="auto"), sa.Column("is_admin", sa.Boolean(), server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
    elif "is_admin" not in {column["name"] for column in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=True))

    inspector = None if context.is_offline_mode() else inspect(op.get_bind())
    tables = set() if inspector is None else set(inspector.get_table_names())
    created_courses = "courses" not in tables
    if created_courses:
        op.create_table("courses",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("course_id", sa.String(64), nullable=False, unique=True),
            sa.Column("course_name", sa.String(128)), sa.Column("address", sa.String(256)),
            sa.Column("default_latitude", sa.String(20)), sa.Column("default_longitude", sa.String(20)),
            sa.Column("weekdays", sa.String(10), server_default="1,2,3,4,5"), sa.Column("teacher_name", sa.String(64)),
            sa.Column("creator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true()), sa.Column("has_captcha", sa.Boolean(), server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
    course_columns = {
        "address", "default_latitude", "default_longitude", "weekdays", "teacher_name", "has_captcha"
    } if created_courses else {column["name"] for column in inspector.get_columns("courses")}
    for name, column in [
        ("address", sa.Column("address", sa.String(256))),
        ("default_latitude", sa.Column("default_latitude", sa.String(20))),
        ("default_longitude", sa.Column("default_longitude", sa.String(20))),
        ("weekdays", sa.Column("weekdays", sa.String(10), server_default="1,2,3,4,5")),
        ("teacher_name", sa.Column("teacher_name", sa.String(64))),
        ("has_captcha", sa.Column("has_captcha", sa.Boolean(), server_default=sa.false())),
    ]:
        if name not in course_columns:
            op.add_column("courses", column)

    if "course_members" not in tables:
        op.create_table("course_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("joined_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "course_id", name="uk_user_course"),
        )
    if "sign_logs" not in tables:
        op.create_table("sign_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("active_id", sa.String(64)), sa.Column("enc", sa.String(128)),
            sa.Column("status", sa.String(20), server_default="pending"), sa.Column("message", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )

    op.create_table("refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table("sign_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_active_id", sa.String(64), nullable=False),
        sa.Column("current_enc", sa.String(128), nullable=False),
        sa.Column("latitude", sa.String(20)), sa.Column("longitude", sa.String(20)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("course_id", "external_active_id", name="uk_activity_course_external"),
    )
    op.create_index("ix_sign_activities_course_id", "sign_activities", ["course_id"])
    op.create_index("ix_sign_activities_status", "sign_activities", ["status"])

    op.create_table("sign_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("sign_activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False), sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(128)), sa.Column("lease_expires_at", sa.DateTime()),
        sa.Column("next_attempt_at", sa.DateTime()), sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text()), sa.Column("result_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.UniqueConstraint("activity_id", "user_id", name="uk_task_activity_user"),
    )
    op.create_index("ix_sign_tasks_status", "sign_tasks", ["status"])
    op.create_index("ix_sign_tasks_user_id", "sign_tasks", ["user_id"])

    op.create_table("outbox_events",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False), sa.Column("published_at", sa.DateTime()),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_outbox_unpublished", "outbox_events", ["published_at", "available_at"])


def downgrade():
    op.drop_table("outbox_events")
    op.drop_table("sign_tasks")
    op.drop_table("sign_activities")
    op.drop_table("refresh_tokens")
    for column in ["has_captcha", "teacher_name", "weekdays", "default_longitude", "default_latitude", "address"]:
        op.drop_column("courses", column)
    op.drop_column("users", "is_admin")
