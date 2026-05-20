from __future__ import annotations

from inflab.config import ObjectStorageSettings
from inflab.object_store import S3ObjectStore


class FakeS3Client:
    def __init__(self) -> None:
        self.puts = []
        self.uploads = []
        self.downloads = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.uploads.append((filename, bucket, key))

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        self.downloads.append((bucket, key, filename))

    def generate_presigned_url(self, operation: str, **kwargs) -> str:
        params = kwargs["Params"]
        expires_in = kwargs["ExpiresIn"]
        return f"https://object-store/{params['Bucket']}/{params['Key']}?expires={expires_in}"


def test_s3_object_store_uploads_bytes(monkeypatch) -> None:
    fake_client = FakeS3Client()

    def fake_boto3_client(*args, **kwargs):
        assert kwargs["endpoint_url"] == "http://minio:9000"
        return fake_client

    monkeypatch.setattr("inflab.object_store.boto3.client", fake_boto3_client)
    store = S3ObjectStore(
        ObjectStorageSettings(
            endpoint_url="http://minio:9000",
            bucket_name="inflab",
            access_key_id="key",
            secret_access_key="secret",
        )
    )

    stored = store.upload_bytes("reports/a.md", b"hello", content_type="text/markdown")

    assert stored.uri == "s3://inflab/reports/a.md"
    assert stored.size_bytes == 5
    assert stored.presigned_url == "https://object-store/inflab/reports/a.md?expires=3600"
    assert fake_client.puts[0]["ContentType"] == "text/markdown"
