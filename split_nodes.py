"""RH Setup and Media nodes; reuse the RH execution/API and resource paths."""

from __future__ import annotations

import json

from .nodes import FeiHouEasyH3, MAX_MEDIA, _canonical_mode, _media_records_from_inputs
from .production_continuation import (
    FeiHouEasyH3ContinuousOutput,
    apply_guide,
    prepare_setup,
)

MEDIA_TYPE = "FEIHOU_H3_RH_MEDIA"


class FeiHouEasyH3RHMedia:
    CATEGORY = "FeiHou Easy H3"
    FUNCTION = "media"
    RETURN_TYPES = (MEDIA_TYPE,)
    RETURN_NAMES = ("h3_media",)
    DESCRIPTION = "RH 媒体载入：9 图 / 3 视频 / 3 音频，使用原有 RH 上传通道和 input 资源。接 Setup 的 h3_media。"

    @classmethod
    def INPUT_TYPES(cls):
        # Same transport as the RH main node; no server-wide resource scan.
        optional = {}
        for index in range(1, MAX_MEDIA + 1):
            for name in (f"media_{index}", f"media_type_{index}", f"media_trim_{index}"):
                optional[name] = ("STRING", {"default": "", "hidden": True})
        optional["embedded_media_json"] = ("STRING", {"default": "", "multiline": True, "hidden": True})
        return {"required": {}, "optional": optional,
                "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO"}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Reuse RH's file-aware fingerprint, so replacing media invalidates Setup.
        return FeiHouEasyH3.IS_CHANGED(**kwargs)

    @staticmethod
    def media(embedded_media_json="", extra_pnginfo=None, unique_id=None, **kwargs):
        records = _media_records_from_inputs(
            {**kwargs, "embedded_media_json": embedded_media_json}, extra_pnginfo, unique_id)
        return ({"schema": 1, "source": "feihou_easy_h3_rh_media", "records": records},)


class FeiHouEasyH3RHSetup(FeiHouEasyH3):
    DESCRIPTION = (
        "RH 生成设置：媒体从独立 Media 输入；其他参数、API 设置、鉴权计费与 RH 主节点相同。"
        "接续由制作包加载器和接续合并节点处理，一采/二采沿用外部工作流。"
    )

    @classmethod
    def INPUT_TYPES(cls):
        types = FeiHouEasyH3.INPUT_TYPES()
        types["required"] = {
            "h3_media": (MEDIA_TYPE, {"tooltip": "接 FeiHou Easy H3 Media · RH。"}),
            **types["required"],
        }
        return types

    @classmethod
    def generate(cls, h3_media=None, **kwargs):
        # Legacy internal-runner controls must not silently bypass the user's samplers.
        if kwargs.pop("continuous_generation", False):
            raise ValueError("旧版 Setup 内部接续已迁移：请使用制作包 production_shot + 接续合并，保留外部一采/二采链路。")
        kwargs.pop("continuous_context_frames", None)
        kwargs.pop("production_plan", None)
        if isinstance(h3_media, dict) and h3_media.get("schema") == 1:
            records = h3_media.get("records") or []
            if _canonical_mode(kwargs.get("mode", "image")) == "image" and not kwargs.get("production_shot"):
                records = [r for r in records if r.get("media_type") == "image"][:2]
            # The connected Media is authoritative, not stale preview widgets on Setup.
            for index in range(1, MAX_MEDIA + 1):
                for prefix in ("media_", "media_type_", "media_trim_"):
                    kwargs.pop(f"{prefix}{index}", None)
            kwargs["embedded_media_json"] = json.dumps(records, ensure_ascii=False)
        kwargs, continuation = prepare_setup(kwargs)
        model, second_model, context = super().generate(**kwargs)
        return model, second_model, apply_guide(context, continuation)


class FeiHouEasyH3RHContinuousOutput(FeiHouEasyH3ContinuousOutput):
    """Legacy RH packed-output unpacker, retained for saved class/type IDs."""
