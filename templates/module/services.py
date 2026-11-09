# app/modules/sample/services.py
from app.modules.sample.constants import SAMPLE_RETRIEVED_MSG


class SampleService:
    """Business logic for the sample module.

    Owns tables? Add models.py + repositories.py, and wrap writes in
    `async with db.begin():` — app/modules/auth is the worked example.
    """

    @staticmethod
    async def get_sample_data() -> tuple[dict, str]:
        return {"message": "Hello from the sample module!"}, SAMPLE_RETRIEVED_MSG
