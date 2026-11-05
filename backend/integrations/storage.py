"""Object storage adapter (MTS §5 `integrations`, §14). One interface; the provider is configuration.

- `s3`: any S3-compatible store: MinIO locally, the provider chosen under P-10 in production.
- `local`: files under MEDIA_ROOT, for tests and machines without object storage.
Private storage holds what shoppers must never reach (3D drafts and sources, MTS §4): a separate folder or
bucket that no public route serves; staff preview it through short-lived signed URLs.
Keys are content-addressed (the file's hash), so a stored file never changes and can be cached for good.
"""

from pathlib import Path
from typing import Any, Protocol

from django.conf import settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Key escapes the storage root.")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self, bucket: str, public: bool = True) -> None:
        import boto3

        self.bucket = bucket
        self.public = public
        self.client: Any = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION or None,
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable" if self.public else "private, no-store",
        )

    def get(self, key: str) -> bytes:
        return bytes(self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read())

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def storage() -> Storage:
    """Public media, served at /media/ through the CDN."""
    if settings.MEDIA_STORAGE == "s3":
        return S3Storage(settings.MEDIA_BUCKET)
    return LocalStorage(Path(settings.MEDIA_ROOT))


def private_storage() -> Storage:
    """Never served publicly."""
    if settings.MEDIA_STORAGE == "s3":
        return S3Storage(settings.MEDIA_PRIVATE_BUCKET, public=False)
    return LocalStorage(Path(settings.MEDIA_PRIVATE_ROOT))
