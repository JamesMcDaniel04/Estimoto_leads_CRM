"""Unique non-blank lead email.

Existing duplicate-email leads (possible under the old read-then-insert
ingestion race) are merged first: the oldest lead survives, children are
reassigned to it, the rest are deleted. Then the partial unique index makes
the race impossible going forward.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

CHILD_TABLES = ("email_messages", "meetings", "activities")


def upgrade() -> None:
    bind = op.get_bind()
    dupes = bind.execute(
        sa.text(
            "SELECT email, MIN(id) AS keep FROM leads"
            " WHERE email != '' GROUP BY email HAVING COUNT(*) > 1"
        )
    ).fetchall()
    for email_value, keep_id in dupes:
        params = {"email": email_value, "keep": keep_id}
        for table in CHILD_TABLES:
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET lead_id = :keep WHERE lead_id IN"
                    " (SELECT id FROM leads WHERE email = :email AND id != :keep)"
                ),
                params,
            )
        bind.execute(
            sa.text("DELETE FROM leads WHERE email = :email AND id != :keep"), params
        )

    # A database adopted from create_all after the model gained this index
    # already has it — stamping starts such databases at the baseline, so
    # this migration must tolerate the index existing.
    existing = {ix["name"] for ix in sa.inspect(bind).get_indexes("leads")}
    if "uq_leads_email_nonblank" not in existing:
        op.create_index(
            "uq_leads_email_nonblank",
            "leads",
            ["email"],
            unique=True,
            sqlite_where=sa.text("email != ''"),
            postgresql_where=sa.text("email != ''"),
        )


def downgrade() -> None:
    op.drop_index("uq_leads_email_nonblank", table_name="leads")
