"""S3-compatible object storage helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.config import Config

from inflab.config import ObjectStorageSettings


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    key: str
    uri: str
    size_bytes: int
    sha256: str
    presigned_url: str | None = None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class S3ObjectStore:
    def __init__(self, settings: ObjectStorageSettings) -> None:
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            region_name=settings.region_name,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key.get_secret_value(),
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def uri(self, key: str) -> str:
        return f"s3://{self.settings.bucket_name}/{key}"

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        self.client.put_object(
            Bucket=self.settings.bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return StoredObject(
            bucket=self.settings.bucket_name,
            key=key,
            uri=self.uri(key),
            size_bytes=len(data),
            sha256=_sha256_bytes(data),
            presigned_url=self.presign_get(key),
        )

    def upload_file(self, key: str, path: Path) -> StoredObject:
        self.client.upload_file(str(path), self.settings.bucket_name, key)
        return StoredObject(
            bucket=self.settings.bucket_name,
            key=key,
            uri=self.uri(key),
            size_bytes=path.stat().st_size,
            sha256=_sha256_file(path),
            presigned_url=self.presign_get(key),
        )

    def download_file(self, key: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.settings.bucket_name, key, str(path))

    def presign_get(self, key: str, *, expires_seconds: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.bucket_name, "Key": key},
            ExpiresIn=expires_seconds,
        )
