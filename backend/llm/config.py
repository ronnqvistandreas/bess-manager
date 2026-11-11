"""Resolve active AI Analyst provider configuration from settings."""

DEFAULT_PROVIDER = "anthropic"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_GOOGLE_MODEL = "gemini-3.8-flash"
DEFAULT_GOOGLE_THINKING_LEVEL = "low"
DEFAULT_COPILOT_MODEL = "auto"
DEFAULT_COPILOT_REASONING_EFFORT = "low"


def resolve_provider_config(
    section: dict,
    provider: str | None = None,
    overrides: dict | None = None,
) -> dict:
    """Merge saved settings with optional overrides for a single provider.

    Returns a flat dict with keys: provider, enabled, api_key, model,
    thinking_level (google only).
    """
    overrides = overrides or {}
    active_provider = provider or section.get("provider", DEFAULT_PROVIDER)

    anthropic = dict(section.get("anthropic", {}))
    google = dict(section.get("google", {}))
    copilot = dict(section.get("copilot", {}))

    if "anthropic" in overrides:
        anthropic.update(overrides["anthropic"])
    if "google" in overrides:
        google.update(overrides["google"])
    if "copilot" in overrides:
        copilot.update(overrides["copilot"])

    enabled = section.get("enabled", True)
    if "enabled" in overrides:
        enabled = overrides["enabled"]

    if active_provider == "google":
        return {
            "provider": "google",
            "enabled": enabled,
            "api_key": google.get("api_key", ""),
            "model": google.get("model", DEFAULT_GOOGLE_MODEL),
            "thinking_level": google.get(
                "thinking_level", DEFAULT_GOOGLE_THINKING_LEVEL
            ),
        }

    if active_provider == "copilot":
        return {
            "provider": "copilot",
            "enabled": enabled,
            "api_key": copilot.get("github_token", ""),
            "model": copilot.get("model", DEFAULT_COPILOT_MODEL),
            "reasoning_effort": copilot.get(
                "reasoning_effort", DEFAULT_COPILOT_REASONING_EFFORT
            ),
        }

    return {
        "provider": "anthropic",
        "enabled": enabled,
        "api_key": anthropic.get("api_key", ""),
        "model": anthropic.get("model", DEFAULT_ANTHROPIC_MODEL),
        "thinking_level": None,
    }
