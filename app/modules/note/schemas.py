# app/modules/note/schemas.py
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import Page
from app.core.responses import APIResponse

TitleField = Annotated[str, Field(min_length=1, max_length=200)]
BodyField = Annotated[str, Field(max_length=10_000)]


class NoteCreateSchema(BaseModel):
    """Payload for creating a note. The owner is the caller, never a field."""

    title: TitleField
    body: BodyField = ""


class NoteUpdateSchema(BaseModel):
    """Partial update: a field left out (or null) keeps its current value."""

    title: TitleField | None = None
    body: BodyField | None = None


class NoteOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: uuid.UUID
    title: str
    body: str
    created_at: datetime
    updated_at: datetime


NoteResponse = APIResponse[NoteOutSchema]
NotePageResponse = APIResponse[Page[NoteOutSchema]]
