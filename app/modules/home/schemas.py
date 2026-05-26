# app/modules/home/schemas.py
from pydantic import BaseModel


class HomeDataOutSchema(BaseModel):
    welcome_message: str
    user_code: str
