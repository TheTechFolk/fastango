# app/modules/note/repositories.py
import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.note.models import Note


class NoteRepository:
    """Data access for notes. Never commits — services own transactions.

    Every read is scoped to an owner. There is deliberately no unscoped
    `get_by_code`: a query that cannot return someone else's note is a stronger
    ownership check than an `if` a service has to remember.
    """

    @staticmethod
    async def list_for_owner(
        db: AsyncSession, owner_code: uuid.UUID, limit: int, offset: int
    ) -> Sequence[Note]:
        """One page of the owner's notes, newest first."""
        result = await db.execute(
            select(Note)
            .where(Note.owner_code == owner_code)
            # `id` breaks ties: without a unique sort key, rows created in the
            # same instant can repeat or vanish between pages.
            .order_by(Note.created_at.desc(), Note.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    @staticmethod
    async def count_for_owner(db: AsyncSession, owner_code: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count()).select_from(Note).where(Note.owner_code == owner_code)
        )
        return result.scalar_one()

    @staticmethod
    async def get_for_owner(
        db: AsyncSession, code: uuid.UUID, owner_code: uuid.UUID
    ) -> Note | None:
        result = await db.execute(
            select(Note).where(Note.code == code, Note.owner_code == owner_code)
        )
        return result.scalars().first()

    @staticmethod
    async def save(db: AsyncSession, note: Note) -> Note:
        """Insert or update within the caller's transaction.

        The refresh is not optional: created_at/updated_at are computed by the
        database, and reading an unloaded attribute later would need a lazy
        load, which async SQLAlchemy refuses.
        """
        db.add(note)
        await db.flush()
        await db.refresh(note)
        return note

    @staticmethod
    async def delete(db: AsyncSession, note: Note) -> None:
        await db.delete(note)
        await db.flush()
