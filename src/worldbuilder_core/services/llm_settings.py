from dataclasses import dataclass

from sqlalchemy.orm import Session

from worldbuilder_core.config import get_settings
from worldbuilder_core.models import AppSetting
from worldbuilder_core.schemas import LLMConfigRead, LLMConfigUpdate

LLM_SETTINGS_KEY = "llm.provider"


@dataclass(frozen=True)
class LLMRuntimeSettings:
    base_url: str
    api_key: str | None
    default_model: str
    chat_model: str | None
    extractor_model: str | None
    summarizer_model: str | None
    critic_model: str | None
    timeout_seconds: float
    max_entities_per_extract: int
    persisted: bool

    def model_for(self, role: str) -> str:
        model = {
            "chat": self.chat_model,
            "extractor": self.extractor_model,
            "summarizer": self.summarizer_model,
            "critic": self.critic_model,
        }.get(role)
        return model or self.default_model


def get_llm_runtime_settings(session: Session) -> LLMRuntimeSettings:
    defaults = get_settings()
    stored = session.get(AppSetting, LLM_SETTINGS_KEY)
    value = stored.value if stored is not None else {}

    return LLMRuntimeSettings(
        base_url=_string_value(value.get("base_url"), defaults.llm_base_url),
        api_key=_optional_string_value(value.get("api_key"), defaults.llm_api_key),
        default_model=_string_value(value.get("default_model"), defaults.llm_model),
        chat_model=_optional_string_value(value.get("chat_model")),
        extractor_model=_optional_string_value(value.get("extractor_model")),
        summarizer_model=_optional_string_value(value.get("summarizer_model")),
        critic_model=_optional_string_value(value.get("critic_model")),
        timeout_seconds=float(value.get("timeout_seconds") or defaults.llm_timeout_seconds),
        max_entities_per_extract=int(value.get("max_entities_per_extract") or defaults.max_entities_per_extract),
        persisted=stored is not None,
    )


def save_llm_runtime_settings(session: Session, payload: LLMConfigUpdate) -> LLMRuntimeSettings:
    current = get_llm_runtime_settings(session)
    api_key = current.api_key
    if payload.clear_api_key:
        api_key = None
    elif payload.api_key is not None:
        api_key = payload.api_key.strip() or None

    value = {
        "base_url": payload.base_url.strip().rstrip("/"),
        "api_key": api_key,
        "default_model": payload.default_model.strip(),
        "chat_model": _clean_optional(payload.chat_model),
        "extractor_model": _clean_optional(payload.extractor_model),
        "summarizer_model": _clean_optional(payload.summarizer_model),
        "critic_model": _clean_optional(payload.critic_model),
        "timeout_seconds": payload.timeout_seconds,
        "max_entities_per_extract": payload.max_entities_per_extract,
    }

    stored = session.get(AppSetting, LLM_SETTINGS_KEY)
    if stored is None:
        stored = AppSetting(key=LLM_SETTINGS_KEY, value=value)
        session.add(stored)
    else:
        stored.value = value
    session.commit()
    return get_llm_runtime_settings(session)


def llm_config_read(runtime: LLMRuntimeSettings) -> LLMConfigRead:
    return LLMConfigRead(
        base_url=runtime.base_url,
        default_model=runtime.default_model,
        chat_model=runtime.chat_model,
        extractor_model=runtime.extractor_model,
        summarizer_model=runtime.summarizer_model,
        critic_model=runtime.critic_model,
        has_api_key=bool(runtime.api_key),
        timeout_seconds=runtime.timeout_seconds,
        max_entities_per_extract=runtime.max_entities_per_extract,
        persisted=runtime.persisted,
    )


def _string_value(value: object, fallback: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _optional_string_value(value: object, fallback: str | None = None) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    return fallback


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None
