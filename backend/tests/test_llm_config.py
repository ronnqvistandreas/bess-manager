"""Tests for AI Analyst provider config resolution."""

from llm.config import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_GOOGLE_THINKING_LEVEL,
    resolve_provider_config,
)
from llm.factory import get_provider


class TestResolveProviderConfig:
    def test_defaults_to_anthropic(self):
        cfg = resolve_provider_config({})
        assert cfg["provider"] == "anthropic"
        assert cfg["api_key"] == ""
        assert cfg["model"] == DEFAULT_ANTHROPIC_MODEL
        assert cfg["enabled"] is True

    def test_nested_anthropic_config(self):
        section = {
            "provider": "anthropic",
            "enabled": True,
            "anthropic": {
                "api_key": "sk-ant-test",
                "model": "claude-opus-4-20250514",
            },
        }
        cfg = resolve_provider_config(section)
        assert cfg["api_key"] == "sk-ant-test"
        assert cfg["model"] == "claude-opus-4-20250514"

    def test_google_provider_config(self):
        section = {
            "provider": "google",
            "google": {
                "api_key": "AIza-test",
                "model": DEFAULT_GOOGLE_MODEL,
                "thinking_level": "high",
            },
        }
        cfg = resolve_provider_config(section)
        assert cfg["provider"] == "google"
        assert cfg["api_key"] == "AIza-test"
        assert cfg["model"] == DEFAULT_GOOGLE_MODEL
        assert cfg["thinking_level"] == "high"

    def test_google_defaults(self):
        section = {"provider": "google", "google": {"api_key": "AIza-test"}}
        cfg = resolve_provider_config(section)
        assert cfg["model"] == DEFAULT_GOOGLE_MODEL
        assert cfg["thinking_level"] == DEFAULT_GOOGLE_THINKING_LEVEL

    def test_overrides_merge(self):
        section = {
            "provider": "anthropic",
            "anthropic": {"api_key": "saved-key", "model": DEFAULT_ANTHROPIC_MODEL},
        }
        cfg = resolve_provider_config(
            section,
            provider="google",
            overrides={"google": {"api_key": "draft-key", "thinking_level": "low"}},
        )
        assert cfg["provider"] == "google"
        assert cfg["api_key"] == "draft-key"


class TestProviderFactory:
    def test_returns_anthropic_provider(self):
        provider = get_provider("anthropic", "sk-test", DEFAULT_ANTHROPIC_MODEL)
        from llm.anthropic_provider import AnthropicProvider

        assert isinstance(provider, AnthropicProvider)

    def test_returns_google_provider(self):
        provider = get_provider(
            "google", "AIza-test", DEFAULT_GOOGLE_MODEL, thinking_level="low"
        )
        from llm.google_provider import GoogleProvider

        assert isinstance(provider, GoogleProvider)
