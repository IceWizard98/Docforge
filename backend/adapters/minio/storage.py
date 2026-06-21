import asyncio
import os
from functools import lru_cache
from io import BytesIO

from minio import Minio

from config.settings import get_settings


@lru_cache
def _get_minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_use_ssl,
    )


def _sanitize_path(path: str) -> str:
    if ".." in path.split("/"):
        raise ValueError(f"Invalid path: {path} contains path traversal characters")
    return os.path.normpath(path).lstrip("/")


class MinioStorageAdapter:
    def __init__(self):
        self.client = _get_minio_client()
        self.bucket = get_settings().minio_bucket

    async def upload(self, path: str, data: bytes, content_type: str) -> str:
        sanitized = _sanitize_path(path)
        stream = BytesIO(data)
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket, sanitized, stream, len(data),
            content_type=content_type,
        )
        return sanitized

    async def download(self, path: str) -> bytes:
        sanitized = _sanitize_path(path)
        response = await asyncio.to_thread(
            self.client.get_object, self.bucket, sanitized
        )
        try:
            return await asyncio.to_thread(response.read)
        finally:
            response.close()
            response.release_conn()

    async def delete(self, path: str) -> None:
        sanitized = _sanitize_path(path)
        await asyncio.to_thread(
            self.client.remove_object, self.bucket, sanitized
        )

    async def exists(self, path: str) -> bool:
        sanitized = _sanitize_path(path)
        try:
            await asyncio.to_thread(
                self.client.stat_object, self.bucket, sanitized
            )
            return True
        except Exception:
            return False

    def get_url(self, path: str, expires: int = 3600) -> str:
        sanitized = _sanitize_path(path)
        return self.client.presigned_get_object(self.bucket, sanitized, expires=expires)
