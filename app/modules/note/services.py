# app/modules/note/services.py
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.pagination import Page, PageParams
from app.database import atomic, get_db_session
from app.modules.note.constants import (
    NOTE_CREATED_MSG,
    NOTE_DELETED_MSG,
    NOTE_LIST_MSG,
    NOTE_NOT_FOUND_MSG,
    NOTE_RETRIEVED_MSG,
    NOTE_UPDATED_MSG,
)
from app.modules.note.models import Note
from app.modules.note.repositories import NoteRepository
from app.modules.note.schemas import NoteCreateSchema, NoteOutSchema, NoteUpdateSchema


class NoteService:
    """CRUD on the caller's own notes. Returns (data, message); raises on failure.

    One instance is one request, acting as `owner_code`. Every lookup is scoped
    to that owner, so someone else's note is a 404 — not a 403, which would
    confirm the note exists.
    """

    def __init__(self, owner_code: uuid.UUID) -> None:
        self.owner_code = owner_code

    async def list_page(self, params: PageParams) -> tuple[Page[NoteOutSchema], str]:
        db = get_db_session()
        notes = await NoteRepository.list_for_owner(
            db, self.owner_code, params.limit, params.offset
        )
        total = await NoteRepository.count_for_owner(db, self.owner_code)
        page = Page[NoteOutSchema](
            items=[NoteOutSchema.model_validate(note) for note in notes],
            limit=params.limit,
            offset=params.offset,
            total=total,
        )
        return page, NOTE_LIST_MSG

    async def get(self, code: uuid.UUID) -> tuple[NoteOutSchema, str]:
        note = await self._get_or_404(get_db_session(), code)
        return NoteOutSchema.model_validate(note), NOTE_RETRIEVED_MSG

    async def create(self, data: NoteCreateSchema) -> tuple[NoteOutSchema, str]:
        db = get_db_session()
        async with atomic(db):
            # owner_code comes from the token, never from the request body.
            note = Note(owner_code=self.owner_code, **data.model_dump())
            await NoteRepository.save(db, note)
        return NoteOutSchema.model_validate(note), NOTE_CREATED_MSG

    async def update(self, code: uuid.UUID, data: NoteUpdateSchema) -> tuple[NoteOutSchema, str]:
        db = get_db_session()
        # Load, check, then write — all inside one transaction.
        async with atomic(db):
            note = await self._get_or_404(db, code)
            for field, value in data.model_dump(exclude_none=True).items():
                setattr(note, field, value)
            await NoteRepository.save(db, note)
        return NoteOutSchema.model_validate(note), NOTE_UPDATED_MSG

    async def delete(self, code: uuid.UUID) -> tuple[None, str]:
        db = get_db_session()
        async with atomic(db):
            note = await self._get_or_404(db, code)
            await NoteRepository.delete(db, note)
        return None, NOTE_DELETED_MSG

    async def _get_or_404(self, db: AsyncSession, code: uuid.UUID) -> Note:
        note = await NoteRepository.get_for_owner(db, code, self.owner_code)
        if note is None:
            raise NotFoundException(NOTE_NOT_FOUND_MSG)
        return note
