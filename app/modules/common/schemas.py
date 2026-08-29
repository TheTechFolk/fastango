# app/modules/common/schemas.py
"""
Fastango — Shared Schema Field Types

Annotated types reused across module schemas, so a rule like "how an email is
normalized" is defined once. The point is correctness rather than brevity: if
two schemas normalize an email differently they disagree about what the same
address means, and the failure is silent — an account you can create but not
log in to.

A type earns a place here once a second module needs it.
"""

from typing import Annotated

from pydantic import BeforeValidator, EmailStr, Field


def _normalize_email(value: str) -> str:
    """Trim and lowercase so ` Me@Example.com ` and `me@example.com` are one account."""
    # BeforeValidator runs ahead of EmailStr parsing, so the value here is
    # still raw JSON and may be any type — hence the guard.
    return value.strip().lower() if isinstance(value, str) else value


# Runs *before* EmailStr, which is what lets a padded address validate at all;
# an after-validator would only see values EmailStr had already accepted.
EmailField = Annotated[EmailStr, BeforeValidator(_normalize_email)]

# bcrypt silently truncates input past 72 bytes, so the cap belongs at the edge
# rather than in the service.
NewPasswordField = Annotated[str, Field(min_length=8, max_length=72)]

# Deliberately looser than NewPasswordField. Enforcing the 8-char minimum on
# login would answer a short guess with 422 instead of 401 — leaking the
# password policy and separating "malformed" from "wrong", which is exactly
# what a generic credentials message exists to prevent.
ExistingPasswordField = Annotated[str, Field(min_length=1, max_length=72)]
