import asyncio
from functools import lru_cache

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


class MinioStorageAdapter:
    def __init__(self):
        self.client = _get_minio_client()
        self.bucket = get_settings().minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    async def upload(self, path: str, data: bytes, content_type: str) -> str:
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket, path, data, len(data),
            content_type=content_type,
        )
        return path

    async def download(self, path: str) -> bytes:
        response = await asyncio.to_thread(
            self.client.get_object, self.bucket, path
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(
            self.client.remove_object, self.bucket, path
        )

    async def exists(self, path: str) -> bool:
        try:
            await asyncio.to_thread(
                self.client.stat_object, self.bucket, path
            )
            return True
        except Exception:
            return False

    def get_url(self, path: str, expires: int = 3600) -> str:
        return self.client.presigned_get_object(self.bucket, path, expires=expires)
