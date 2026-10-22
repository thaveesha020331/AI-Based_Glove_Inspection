"""store per-class risk probabilities

Revision ID: 5f3b7a9d2c11
Revises: 7e1d5c4def20
"""

from alembic import op
import sqlalchemy as sa


revision = "5f3b7a9d2c11"
down_revision = "7e1d5c4def20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("prediction_records") as batch_op:
        batch_op.add_column(sa.Column("probability_scores", sa.JSON(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE prediction_records "
            "SET probability_scores = :empty_scores "
            "WHERE probability_scores IS NULL"
        ).bindparams(empty_scores="{}")
    )
    with op.batch_alter_table("prediction_records") as batch_op:
        batch_op.alter_column("probability_scores", existing_type=sa.JSON(), nullable=False)


def downgrade():
    with op.batch_alter_table("prediction_records") as batch_op:
        batch_op.drop_column("probability_scores")
