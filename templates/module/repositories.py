# app/modules/sample/repositories.py
# Async DB read/write operations. Never commits — services own transactions.
# Delete this file if the module owns no tables.
#
# Example:
#
# import uuid
#
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession
#
# from app.modules.sample.models import Sample
#
#
# class SampleRepository:
#     @staticmethod
#     async def get_by_code(db: AsyncSession, sample_code: uuid.UUID) -> Sample | None:
#         result = await db.execute(select(Sample).where(Sample.sample_code == sample_code))
#         return result.scalars().first()
#
#     @staticmethod
#     async def create(db: AsyncSession, sample: Sample) -> Sample:
#         db.add(sample)
#         await db.flush()
#         await db.refresh(sample)
#         return sample
