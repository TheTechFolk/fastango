# app/modules/note/router.py
import uuid

from fastapi import APIRouter, Depends, status

from app.core.decorators import api_response
from app.core.pagination import PageParams, page_params
from app.core.responses import APIResponse, error_responses
from app.core.security import get_current_user_code
from app.modules.note.schemas import (
    NoteCreateSchema,
    NotePageResponse,
    NoteResponse,
    NoteUpdateSchema,
)
from app.modules.note.services import NoteService

# No prefix/tags here — apps.py owns those. Mounted private, so every route
# already requires a valid access token.
router = APIRouter()


@router.get("", response_model=NotePageResponse)
@api_response()
async def list_notes(
    params: PageParams = Depends(page_params),
    user_code: uuid.UUID = Depends(get_current_user_code),
):
    """The caller's notes, newest first."""
    return await NoteService(user_code).list_page(params)


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
@api_response()
async def create_note(
    payload: NoteCreateSchema, user_code: uuid.UUID = Depends(get_current_user_code)
):
    """Create a note owned by the caller."""
    return await NoteService(user_code).create(payload)


@router.get("/{code}", response_model=NoteResponse, responses=error_responses(404))
@api_response()
async def get_note(code: uuid.UUID, user_code: uuid.UUID = Depends(get_current_user_code)):
    """One of the caller's notes."""
    return await NoteService(user_code).get(code)


@router.patch("/{code}", response_model=NoteResponse, responses=error_responses(404))
@api_response()
async def update_note(
    code: uuid.UUID,
    payload: NoteUpdateSchema,
    user_code: uuid.UUID = Depends(get_current_user_code),
):
    """Change the fields sent; leave the rest alone."""
    return await NoteService(user_code).update(code, payload)


@router.delete("/{code}", response_model=APIResponse[None], responses=error_responses(404))
@api_response()
async def delete_note(code: uuid.UUID, user_code: uuid.UUID = Depends(get_current_user_code)):
    """Delete one of the caller's notes."""
    return await NoteService(user_code).delete(code)
