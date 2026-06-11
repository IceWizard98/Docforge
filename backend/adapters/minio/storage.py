import asyncio
import os
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


def _sanitize_path(path: str) -> str:
    if ".." in path.split("/"):
        raise ValueError(f"Invalid path: {path} contains path traversal characters")
    return os.path.normpath(path).lstrip("/")


class MinioStorageAdapter:
    def __init__(self):
        self.client = _get_minio_client()
        self.bucket = get_settings().minio_bucket

    async def upload(self, path: str, data: bytes, content_type: str, tenant_id: str = "") -> str:
        sanitized = _sanitize_path(path)
        if tenant_id:
            sanitized = f"{tenant_id}/{sanitized}"
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket, sanitized, data, len(data),
            content_type=content_type,
        )
        return sanitized

    async def download(self, path: str, tenant_id: str = "") -> bytes:
        sanitized = _sanitize_path(path)
        if tenant_id:
            sanitized = f"{tenant_id}/{sanitized}"
        response = await asyncio.to_thread(
            self.client.get_object, self.bucket, sanitized
        )
        try:
            return await asyncio.to_thread(response.read)
        finally:
            response.close()
            response.release_conn()

    async def delete(self, path: str, tenant_id: str = "") -> None:
        sanitized = _sanitize_path(path)
        if tenant_id:
            sanitized = f"{tenant_id}/{sanitized}"
        await asyncio.to_thread(
            self.client.remove_object, self.bucket, sanitized
        )

    async def exists(self, path: str, tenant_id: str = "") -> bool:
        sanitized = _sanitize_path(path)
        if tenant_id:
            sanitized = f"{tenant_id}/{sanitized}"
        try:
            await asyncio.to_thread(
                self.client.stat_object, self.bucket, sanitized
            )
            return True
        except Exception:
            return False

    def get_url(self, path: str, expires: int = 3600, tenant_id: str = "") -> str:
        sanitized = _sanitize_path(path)
        if tenant_id:
            sanitized = f"{tenant_id}/{sanitized}"
        return self.client.presigned_get_object(self.bucket, sanitized, expires=expires)
