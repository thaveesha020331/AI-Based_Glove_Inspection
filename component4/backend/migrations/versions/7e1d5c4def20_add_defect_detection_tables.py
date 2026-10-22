"""add persisted image detection tables"""
from alembic import op
import sqlalchemy as sa

revision = "7e1d5c4def20"
down_revision = "39385bd37a8d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "defect_images",
        sa.Column("image_id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(64), sa.ForeignKey("batches.batch_id"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_path", sa.String(500), nullable=False),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("detection_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("analysis_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_defect_images_batch", "defect_images", ["batch_id"])
    op.create_table(
        "defect_detections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("image_id", sa.String(64), sa.ForeignKey("defect_images.image_id"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 5), nullable=False),
        sa.Column("x1", sa.Float, nullable=False), sa.Column("y1", sa.Float, nullable=False),
        sa.Column("x2", sa.Float, nullable=False), sa.Column("y2", sa.Float, nullable=False),
        sa.Column("area_zone", sa.String(30), nullable=False),
    )
    op.create_index("ix_defect_detections_image", "defect_detections", ["image_id"])


def downgrade():
    op.drop_index("ix_defect_detections_image", table_name="defect_detections")
    op.drop_table("defect_detections")
    op.drop_index("ix_defect_images_batch", table_name="defect_images")
    op.drop_table("defect_images")
