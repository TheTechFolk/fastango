# app/core/pagination.py
"""
Fastango — Offset pagination, declared once.

Cursor pagination is deliberately not here: it needs a stable sort key the
template cannot know, and offset is correct until a table is large enough to
make the OFFSET scan hurt. Swap per project when that day comes.
"""

from dataclasses import dataclass

from fastapi import Query
from pydantic import BaseModel

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@dataclass(frozen=True)
class PageParams:
    """Validated limit/offset, resolved by the `page_params` dependency."""

    limit: int
    offset: int


def page_params(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> PageParams:
    """Route dependency: `params: PageParams = Depends(page_params)`.

    The upper bound is not optional — an unbounded `limit` is a one-request
    denial of service against your own database.
    """
    return PageParams(limit=limit, offset=offset)


class Page[T](BaseModel):
    """One page of results plus what the caller needs to ask for the next.

    `total` is optional because counting costs a second query; a repository that
    cannot afford it returns None and the client paginates until short.
    """

    items: list[T]
    limit: int
    offset: int
    total: int | None = None
