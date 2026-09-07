"""Load RunningHub OpenAPI LLM helpers used by Easy H3 prompt optimization."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_PLUGIN_DIR = Path(__file__).resolve().parent
_CUSTOM_NODES_DIR = _PLUGIN_DIR.parent
_RH_ROOT = _CUSTOM_NODES_DIR / "ComfyUI_RH_OpenAPI"

DEFAULT_MODEL = "google/gemini-3.1-flash-lite-preview"
FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "qwen/qwen3-vl-235b-a22b-instruct",
    "qwen/qwen-plus",
    "qwen/qwen-max",
    "deepseek/deepseek-v3.2",
    "deepseek/deepseek-chat",
]
LLM_API_TYPE = "rh-llm-chat-completions"
LLM_APP_CODE_HEADER = "x-rh-llm-app-code"


class RhOpenApiUnavailable(RuntimeError):
    pass


def _ensure_custom_nodes_on_path() -> None:
    path = str(_CUSTOM_NODES_DIR)
    if path not in sys.path:
        sys.path.append(path)


def _import_helpers() -> Dict[str, Any]:
    _ensure_custom_nodes_on_path()
    from ComfyUI_RH_OpenAPI.core.api_key import get_config
    from ComfyUI_RH_OpenAPI.core.billing import perform_fixed_api_balance_precheck
    from ComfyUI_RH_OpenAPI.nodes.llm_chat import (
        DEFAULT_MODEL as RH_DEFAULT_MODEL,
        FALLBACK_MODELS as RH_FALLBACK_MODELS,
        LLM_API_TYPE as RH_LLM_API_TYPE,
        LLM_APP_CODE_HEADER as RH_LLM_APP_CODE_HEADER,
        fetch_llm_models,
        get_llm_app_code,
        post_chat_completion,
        remove_think_tags,
        resolve_llm_base_url,
    )

    return {
        "get_config": get_config,
        "perform_fixed_api_balance_precheck": perform_fixed_api_balance_precheck,
        "fetch_llm_models": fetch_llm_models,
        "get_llm_app_code": get_llm_app_code,
        "post_chat_completion": post_chat_completion,
        "remove_think_tags": remove_think_tags,
        "resolve_llm_base_url": resolve_llm_base_url,
        "DEFAULT_MODEL": RH_DEFAULT_MODEL,
        "FALLBACK_MODELS": list(RH_FALLBACK_MODELS),
        "LLM_API_TYPE": RH_LLM_API_TYPE,
        "LLM_APP_CODE_HEADER": RH_LLM_APP_CODE_HEADER,
    }


_HELPERS: Optional[Dict[str, Any]] = None
_LOAD_ERROR: Optional[str] = None


def load_rh_helpers() -> Dict[str, Any]:
    global _HELPERS, _LOAD_ERROR
    if _HELPERS is not None:
        return _HELPERS
    if not (_RH_ROOT / "__init__.py").is_file():
        raise RhOpenApiUnavailable(
            "缺少 ComfyUI_RH_OpenAPI。RH 平台提示词优化依赖该插件的 LLM Chat 能力。"
        )
    try:
        _HELPERS = _import_helpers()
        return _HELPERS
    except Exception as exc:
        _LOAD_ERROR = f"{type(exc).__name__}: {exc}"
        print(f"[FeiHouEasyH3RH] Failed to load ComfyUI_RH_OpenAPI: {_LOAD_ERROR}")
        raise RhOpenApiUnavailable(
            f"无法导入 ComfyUI_RH_OpenAPI。详情：{_LOAD_ERROR}"
        ) from exc


def default_model(models: List[str] | None = None) -> str:
    preferred = DEFAULT_MODEL
    try:
        preferred = load_rh_helpers().get("DEFAULT_MODEL", DEFAULT_MODEL)
    except Exception:
        pass
    if models:
        return preferred if preferred in models else models[0]
    return preferred


def fetch_models() -> List[str]:
    """Same model list as RH_LLMChat, with a local fallback if OpenAPI is missing."""
    try:
        helpers = load_rh_helpers()
        models = helpers["fetch_llm_models"]()
        if models:
            return list(models)
        return list(helpers.get("FALLBACK_MODELS", FALLBACK_MODELS))
    except Exception:
        return list(FALLBACK_MODELS)
