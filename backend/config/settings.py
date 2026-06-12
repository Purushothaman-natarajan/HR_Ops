from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
import yaml
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    agui_timeout_seconds: int = 300

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""

    chroma_persist_dir: str = "./data/chroma_db"
    rl_alpha: float = 0.1
    rl_gamma: float = 0.9

    # ------------------------------------------------------------------
    # YAML config loaders
    # ------------------------------------------------------------------
    _config_cache: dict = {}

    def _load_yaml(self, name: str) -> dict:
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
    def available_providers(self) -> list[str]:
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.groq_api_key:
            providers.append("groq")
        return providers

    @property
    def llm_is_configured(self) -> bool:
        return len(self.available_providers) > 0


settings = Settings()
