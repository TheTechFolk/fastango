# app/modules/sample/services.py
from app.modules.sample.constants import SAMPLE_RETRIEVED_MSG


class SampleService:
    """Business logic for the sample module."""

    @staticmethod
    async def get_sample_data() -> tuple[dict, str]:
        return {"message": "Hello from the sample module!"}, SAMPLE_RETRIEVED_MSG

    # Writes must own their transaction boundary — get_db() does NOT
    # auto-commit, and uncommitted writes raise at request end:
    #
    # from app.core.exceptions import NotFoundException
    # from app.database import get_db_session
    #
    # async def create_sample(self, data) -> tuple[dict, str]:
    #     db = get_db_session()
    #     async with db.begin():
    #         sample = Sample(title=data.title)
    #         await SampleRepository.create(db, sample)
    #     return {"sample_code": sample.sample_code}, "Created."
