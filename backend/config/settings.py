"""Application settings loaded from environment variables and supplementary YAML configs with in-memory caching."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables (with .env support) and lazily cached YAML configs."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    log_file: str = "./logs/hr_ops.log"
    agui_timeout_seconds: int = 300
    app_role: str = "admin"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    nvidia_api_key: str = ""

    chroma_persist_dir: str = "./data/chroma_db"
    database_url: str = "sqlite:///./backend/data/hr_ops.db"
    auth_secret_key: str = "change-me-in-production"
    rl_alpha: float = 0.1
    rl_gamma: float = 0.9
    rl_batch_size: int = 10

    # ------------------------------------------------------------------
    # YAML config loaders with in-memory caching
    # Each property below delegates to _load_yaml, which reads the
    # corresponding <name>.yaml file once and caches the result for
    # subsequent lookups within the process lifetime.
    # ------------------------------------------------------------------
    _config_cache: dict = {}

    def _load_yaml(self, name: str) -> dict:
        """Read a YAML config file from the config/ directory, caching its contents after the first read."""
        if name not in self._config_cache:
            path = Path(__file__).parent / f"{name}.yaml"
            with open(path) as f:
                self._config_cache[name] = yaml.safe_load(f)
        return self._config_cache[name]

    @property
    def feature_flags(self) -> dict:
        return self._load_yaml("feature_flags")

    @property
    def chunking_config(self) -> dict:
        return self._load_yaml("chunking_config")

    @property
    def model_config_yaml(self) -> dict:
        return self._load_yaml("model_config")

    @property
    def guardrails_config(self) -> dict:
        return self._load_yaml("guardrails_config")

    @property
    def cost_config(self) -> dict:
        return self._load_yaml("cost_config")

    @property
    def compliance_config(self) -> dict:
        return self._load_yaml("compliance_config")

    @property
    def embed_config(self) -> dict:
        return self._load_yaml("embed_config")

    @property
    def roles_config(self) -> dict:
        return self._load_yaml("roles_config")

    @property
    def available_providers(self) -> list[str]:
        """Return a list of LLM provider names for which an API key is configured."""
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
