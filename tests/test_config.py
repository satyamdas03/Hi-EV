from ev.config import get_settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("EV_DATABASE_URL", "postgresql://localhost:5432/hiev_test")
    monkeypatch.setenv("EV_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("EV_PERSONAL_ONLY", "true")
    monkeypatch.setenv("EV_NOTES_PATH", "/tmp/notes")
    monkeypatch.setenv("EV_GITHUB_TOKEN", "ghp_test")
    settings = get_settings()
    assert settings.database_url == "postgresql://localhost:5432/hiev_test"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.personal_only is True
    assert str(settings.notes_path) == "/tmp/notes"
    assert settings.github_token.get_secret_value() == "ghp_test"
