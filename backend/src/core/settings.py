"""Application settings loaded from environment variables and supplementary YAML configs with in-memory caching.

Config is split across two YAML files:
  - app_config.yaml      → feature toggles, guardrails, compliance, RBAC
  - nvidia_config.yaml   → LLM model routing, embedding, cost, chunking, cache, reranker

Loaded lazily on first property access and cached thereafter.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables (with .env support) and lazily cached YAML configs."""

    _project_root = Path(__file__).parent.parent.parent.parent
    model_config = SettingsConfigDict(
        env_file=str(_project_root / ".env"),
        env_file_encoding="utf-8",
    )

    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    log_file: str = "./backend/data/hr_ops.log"
    agui_timeout_seconds: int = 86400
    app_role: str = "admin"
    startup_reindex: bool = True

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    nvidia_api_key: str = ""

    chroma_persist_dir: str = "./backend/data/chroma_db"
    database_url: str = "sqlite:///./backend/data/hr_ops.db"
    auth_secret_key: str = "change-me-in-production"
    rl_alpha: float = 0.1
    rl_gamma: float = 0.9
    rl_batch_size: int = 10

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Ensure that default secrets are overridden in production."""
        if self.environment == "production" and self.auth_secret_key == "change-me-in-production":
            raise ValueError("auth_secret_key must be overridden in production environment.")
        return self

    # ------------------------------------------------------------------
    # YAML loader — reads once, caches forever (per process)
    # ------------------------------------------------------------------
    _config_cache: dict = {}

    def _load_yaml(self, name: str) -> dict:
        """Read a YAML config file from the config/ directory, caching its contents after the first read."""
        if name not in self._config_cache:
            path = Path(__file__).parent.parent.parent / "config" / f"{name}.yaml"
            with open(path) as f:
                self._config_cache[name] = yaml.safe_load(f)
        return self._config_cache[name]

    # ── NVIDIA infrastructure config ───────────────────────────────
    @property
    def nvidia_config(self) -> dict:
        """Full contents of nvidia_config.yaml (embedding, models, cost, chunking, cache, reranker, etc.)."""
        return self._load_yaml("nvidia_config")

    @property
    def embed_config(self) -> dict:
        """Alias for nvidia_config — the sole embedding source.

        Returns the full nvidia_config dict so callers (vector_store,
        semantic_cache, supervisor cache) can access embedding model
        name, dimension, normalization settings, and batch size.
        """
        return self.nvidia_config

    @property
    def model_config_yaml(self) -> dict:
        """Per-agent model routing from nvidia_config.yaml → 'models' key.

        Returns the agents dict with primary/fallback model names,
        cost floors, reasoning effort, and top_p for each agent role.
        Referenced by backend/src/utils/model_router.py.
        """
        return self.nvidia_config.get("models", {})

    @property
    def cost_config(self) -> dict:
        """Model token costs, budgets, alerts, and cost tiers from nvidia_config.yaml → 'cost' key.

        Used by model_router.py for per-run cost calculation and tier-based
        model selection (cheap / standard / premium).
        """
        return self.nvidia_config.get("cost", {})

    @property
    def chunking_config(self) -> dict:
        """Chunking strategy definitions from nvidia_config.yaml → 'chunking' key.

        Contains the default_strategy name and parameters for all six
        pluggable strategies (recursive, fixed_size, semantic, etc.).
        Used by backend/src/memory/chunking/factory.py.
        """
        return self.nvidia_config.get("chunking", {})

    # ── Application-layer config ───────────────────────────────────
    @property
    def app_config(self) -> dict:
        """Full contents of app_config.yaml (feature_flags, guardrails, compliance, roles)."""
        return self._load_yaml("app_config")

    @property
    def feature_flags(self) -> dict:
        """Feature toggle dict from app_config.yaml → 'feature_flags' key.

        Each flag (guardrails.*, rl.enabled, dspy.enabled, etc.) gates
        an entire subsystem. Referenced throughout the codebase to
        conditionally enable/disable runtime behaviour.
        """
        return self.app_config.get("feature_flags", {})

    @property
    def guardrails_config(self) -> dict:
        """Guardrail rule definitions from app_config.yaml → 'guardrails' key.

        Contains per-category (input/output/tool/model) settings such as
        regex patterns, blocked topics, allowed tones, and timeouts.
        Used by backend/src/guardrails/.
        """
        return self.app_config.get("guardrails", {})

    @property
    def compliance_config(self) -> dict:
        """Compliance veto rules from app_config.yaml → 'compliance' key.

        Defines hard veto rules, whether a policy reference is required,
        and escalation roles. Used by backend/src/intelligence/compliance/.
        """
        return self.app_config.get("compliance", {})

    @property
    def roles_config(self) -> dict:
        """RBAC definitions from app_config.yaml → 'roles' key.

        Contains the default app_role and per-role section visibility,
        policy CRUD permissions, and trace/feedback access flags.
        Used by frontend/src/App.tsx for UI gating.
        """
        return self.app_config.get("roles", {})

    @property
    def available_providers(self) -> list[str]:
        """Return a list of LLM provider names for which an API key is configured.

        Checks each known API key field and returns non-empty providers
        in lookup order: openai, anthropic, groq, nvidia.
        """
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.groq_api_key:
            providers.append("groq")
        if self.nvidia_api_key:
            providers.append("nvidia")
        return providers

    @property
    def llm_is_configured(self) -> bool:
        """Return True if at least one LLM provider has been configured with an API key."""
        return len(self.available_providers) > 0


settings = Settings()
