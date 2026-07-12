# app/modules/sample/models.py
# Delete this file if the module owns no database tables — the registry
# handles missing models.py gracefully.
#
# Example table extending the shared timestamp + is_active base:
#
# import uuid
#
# from sqlalchemy import String
# from sqlalchemy.dialects.postgresql import UUID
# from sqlalchemy.orm import Mapped, mapped_column
#
# from app.modules.common.models import CommonFieldBase
#
#
# class Sample(CommonFieldBase):
#     __tablename__ = "sample"
#
#     id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
#     sample_code: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True),
#         default=uuid.uuid4,
#         nullable=False,
#         unique=True,
#         index=True,
#     )
#     title: Mapped[str] = mapped_column(String(255), nullable=False)
