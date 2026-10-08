import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_target_local_ollama_and_minilm() -> None:
    settings = Settings()
    assert settings.ollama_base_url.host == "127.0.0.1"
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.embedding_dimension == 384


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLIP_OLLAMA_MODEL", "llama3.2:3b")
    assert Settings().ollama_model == "llama3.2:3b"


@pytest.mark.parametrize("field,value", [("ollama_timeout_seconds", 0), ("environment", "staging")])
def test_invalid_settings_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({field: value})
