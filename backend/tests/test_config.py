from pydantic import SecretStr

from inflab.config import AppSettings


def test_settings_load_flat_backend_environment(monkeypatch) -> None:
    monkeypatch.setenv("INFLAB_ENVIRONMENT", "test")
    monkeypatch.setenv("INFLAB_DATABASE_URL", "postgresql+psycopg://u:p@db:5432/inflab")
    monkeypatch.setenv("INFLAB_REDIS_URL", "redis://redis:6379/2")
    monkeypatch.setenv("INFLAB_S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("INFLAB_S3_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("INFLAB_SSH_KNOWN_HOSTS_POLICY", "strict")
    monkeypatch.setenv("INFLAB_LLM_PROVIDER", "openai_compatible")

    settings = AppSettings()

    assert settings.environment == "test"
    assert settings.database.url == "postgresql+psycopg://u:p@db:5432/inflab"
    assert settings.redis.url == "redis://redis:6379/2"
    assert settings.object_storage.endpoint_url == "http://minio:9000"
    assert settings.object_storage.secret_access_key == SecretStr("secret")
    assert settings.ssh.known_hosts_policy == "strict"
    assert settings.llm_provider.provider == "openai_compatible"
