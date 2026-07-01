from autograde_core.config import Settings


def test_defaults_and_dsn(monkeypatch) -> None:
    for var in (
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "AUTOGRADE_ENV",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings(_env_file=None)

    assert settings.env == "dev"
    assert settings.llm_backend == "local"
    dsn = settings.postgres_dsn
    assert dsn.startswith("postgresql+psycopg://")
    assert ":5432/autograde" in dsn


def test_alias_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("AUTOGRADE_ENV", "staging")
    settings = Settings(_env_file=None)
    assert settings.env == "staging"
