from dataclasses import dataclass
from functools import lru_cache
import os


DEFAULT_MODEL_ID = "wso2/tool-poisoning-detection"


@dataclass(frozen=True)
class Settings:
    hf_token: str | None
    model_source: str
    thread_count: int
    use_torch_compile: bool


def _resolve_model_source() -> str:
    model_source = os.getenv("MODEL_SOURCE")
    if model_source:
        return model_source

    return os.getenv("HF_MODEL_ID", DEFAULT_MODEL_ID)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        hf_token=os.getenv("HF_TOKEN") or None,
        model_source=_resolve_model_source(),
        thread_count=int(os.getenv("MODEL_THREAD_COUNT", "4")),
        use_torch_compile=os.getenv("USE_TORCH_COMPILE", "1").lower()
        not in {"0", "false", "no"},
    )
