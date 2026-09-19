from ev.config import get_settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("EV_DATABASE_URL", "postgresql://localhost:5432/hiev_test")
    monkeypatch.setenv("EV_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("EV_PERSONAL_ONLY", "true")
    monkeypatch.setenv("EV_NOTES_PATH", "/tmp/notes")
    monkeypatch.setenv("EV_GITHUB_TOKEN", "ghp_test")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.database_url == "postgresql://localhost:5432/hiev_test"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.personal_only is True
    assert str(settings.notes_path) == "/tmp/notes"
    assert settings.github_token.get_secret_value() == "ghp_test"


def test_phase_b_feature_flags_default():
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.enable_reasoning_router is False
    assert settings.llm_stream_enabled is True
    assert settings.guard_llm_enabled is True
    assert settings.guard_caution_threshold == 0.6
    assert settings.guard_block_patterns == []
    assert settings.guard_untrusted_downgrade_tier == 1


def test_phase_b_feature_flags_from_env(monkeypatch):
    monkeypatch.setenv("EV_ENABLE_REASONING_ROUTER", "true")
    monkeypatch.setenv("EV_LLM_STREAM_ENABLED", "false")
    monkeypatch.setenv("EV_GUARD_LLM_ENABLED", "false")
    monkeypatch.setenv("EV_GUARD_CAUTION_THRESHOLD", "0.8")
    monkeypatch.setenv("EV_GUARD_BLOCK_PATTERNS", "ignore previous,system override")
    monkeypatch.setenv("EV_GUARD_UNTRUSTED_DOWNGRADE_TIER", "0")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.enable_reasoning_router is True
    assert settings.llm_stream_enabled is False
    assert settings.guard_llm_enabled is False
    assert settings.guard_caution_threshold == 0.8
    assert settings.guard_block_patterns == ["ignore previous", "system override"]
    assert settings.guard_untrusted_downgrade_tier == 0
