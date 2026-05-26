# app/core/storage.py
import logging
from typing import BinaryIO

from app.config import settings

logger = logging.getLogger("fastango.storage")


class S3StorageService:
    """
    AWS S3 cloud storage service layer.

    Wraps boto3 S3 operations behind a clean async-friendly interface.
    All methods are structured as async to fit into the FastAPI dependency
    injection model, even though boto3 calls are sync internally.
    For true async S3, swap boto3 with aiobotocore.
    """

    def __init__(self) -> None:
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
        self.region = settings.AWS_S3_REGION
        self._client = None

    def _get_client(self):
        """Lazily initialize the boto3 S3 client."""
        if self._client is None:
            try:
                import boto3

                self._client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=self.region,
                )
            except ImportError:
                logger.warning("boto3 is not installed. S3 operations will be mocked.")
        return self._client

    async def upload_file(
        self,
        file_obj: BinaryIO,
        object_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload a file-like object to S3.

        Args:
            file_obj: An open file-like binary object.
            object_key: The destination key (path) within the S3 bucket.
            content_type: MIME type of the file.

        Returns:
            The public URL of the uploaded object.
        """
        client = self._get_client()
        if client is None:
            logger.info("[S3 MOCK] upload_file: key=%s", object_key)
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{object_key}"

        client.upload_fileobj(
            file_obj,
            self.bucket_name,
            object_key,
            ExtraArgs={"ContentType": content_type},
        )
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{object_key}"

    async def delete_file(self, object_key: str) -> bool:
        """
        Delete an object from S3.

        Args:
            object_key: The key of the object to delete.

        Returns:
            True if deletion succeeded, False otherwise.
        """
        client = self._get_client()
        if client is None:
            logger.info("[S3 MOCK] delete_file: key=%s", object_key)
            return True

        client.delete_object(Bucket=self.bucket_name, Key=object_key)
        return True

    async def generate_presigned_url(
        self,
        object_key: str,
        expiry_seconds: int = 3600,
    ) -> str | None:
        """
        Generate a time-limited pre-signed URL for accessing a private S3 object.

        Args:
            object_key: The S3 key of the object.
            expiry_seconds: Number of seconds until the URL expires.

        Returns:
            A pre-signed URL string, or None on failure.
        """
        client = self._get_client()
        if client is None:
            logger.info("[S3 MOCK] presigned_url: key=%s", object_key)
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{object_key}?mock=1"

        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": object_key},
            ExpiresIn=expiry_seconds,
        )
        return url


# Singleton instance for import convenience
storage_service = S3StorageService()
