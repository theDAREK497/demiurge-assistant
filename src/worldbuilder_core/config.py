from functools import lru_cache
from os import getenv

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = "sqlite:///./worldbuilder.sqlite3"
    api_prefix: str = "/api"
    app_name: str = "Worldbuilder Core"
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_api_key: str | None = None
    llm_model: str = "local-model"
    llm_timeout_seconds: float = 120.0
    max_entities_per_extract: int = 12


@lru_cache
def get_settings() -> Settings:
    defaults = Settings()
    return Settings(
        database_url=getenv("WORLDBUILDER_DATABASE_URL", defaults.database_url),
        api_prefix=getenv("WORLDBUILDER_API_PREFIX", defaults.api_prefix),
        llm_base_url=getenv("WORLDBUILDER_LLM_BASE_URL", defaults.llm_base_url),
        llm_api_key=getenv("WORLDBUILDER_LLM_API_KEY") or None,
        llm_model=getenv("WORLDBUILDER_LLM_MODEL", defaults.llm_model),
        llm_timeout_seconds=float(getenv("WORLDBUILDER_LLM_TIMEOUT_SECONDS", str(defaults.llm_timeout_seconds))),
        max_entities_per_extract=int(getenv("WORLDBUILDER_MAX_ENTITIES_PER_EXTRACT", str(defaults.max_entities_per_extract))),
    )
