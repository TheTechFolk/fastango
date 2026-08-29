# app/modules/sample/models.py
# Delete this file if the module owns no database tables — the registry handles
# a missing models.py gracefully. Do not keep it as a comment-only placeholder.
#
# Example table extending the shared timestamp + is_active base:
#
# import uuid
#
# from sqlalchemy import String, Uuid
# from sqlalchemy.orm import Mapped, mapped_column
#
# from app.modules.common.models import CommonFieldBase
#
#
# class Sample(CommonFieldBase):
#     __tablename__ = "sample"
#
#     id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
#     sample_code: Mapped[uuid.UUID] = mapped_column(
#         Uuid(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True, index=True
#     )
#     title: Mapped[str] = mapped_column(String(255), nullable=False)
#
#     # Cross-module foreign keys use the string table name — never an import of
#     # the other module's model class, which is what makes the two independently
#     # deletable. import_all_models() guarantees both are registered first.
#     # owner_id: Mapped[int] = mapped_column(ForeignKey("auth.id", ondelete="CASCADE"))
