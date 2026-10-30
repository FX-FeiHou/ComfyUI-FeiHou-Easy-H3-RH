"""RH Setup and Media nodes; reuse the RH execution/API and resource paths."""

from __future__ import annotations

import json
from collections.abc import Mapping

import torch

from .nodes import FeiHouEasyH3, MAX_AUDIOS, MAX_IMAGES, MAX_MEDIA, MAX_VIDEOS, _canonical_mode, _media_records_from_inputs
from .production_continuation import (
    FeiHouEasyH3ContinuousOutput,
    apply_guide,
    prepare_setup,
)

MEDIA_TYPE = "FEIHOU_H3_RH_MEDIA"
# IMAGE frame sequences on a linked video socket carry no frame rate: H3 runs at 24 fps.
IMAGE_SEQUENCE_FPS = 24.0
SLOT_OFFSETS = {"image": 0, "video": MAX_IMAGES, "audio": MAX_IMAGES + MAX_VIDEOS}


def _plain_audio(audio):
    """Copy an AUDIO payload (VHS returns a lazy mapping) into a plain dict."""
    if not isinstance(audio, Mapping) or "waveform" not in audio:
        return None
    return {"waveform": audio["waveform"], "sample_rate": int(audio.get("sample_rate") or 44100)}


def _linked_input_types(images: int, videos: int, audios: int) -> dict:
    """Optional IMAGE / VIDEO / AUDIO sockets: image_N, video_N (+ video_N_audio), audio_N."""
    optional = {}
    for index in range(1, images + 1):
        optional[f"image_{index}"] = ("IMAGE", {"tooltip": f"参考图片 {index}，分镜 md 里就是 <Picture {index}>。"})
    for index in range(1, videos + 1):
        optional[f"video_{index}"] = ("IMAGE,VIDEO", {"tooltip":
            f"参考视频 {index}：VIDEO，或 IMAGE 帧序列（按 24fps）。"})
        optional[f"video_{index}_audio"] = ("AUDIO", {"tooltip":
            f"参考视频 {index} 的同步音轨（可选）；接了就替换视频自带的声音。"})
    for index in range(1, audios + 1):
        optional[f"audio_{index}"] = ("AUDIO", {"tooltip": f"独立参考音频 {index}。"})
    return optional


def _linked_items(kwargs: dict, images: int, videos: int, audios: int) -> list:
    """(slot, media_type, value) for every connected socket; slots 1-9 images, 10-12 videos, 13-15 audio."""
    items = []
    for index in range(1, images + 1):
        image = kwargs.get(f"image_{index}")
        if isinstance(image, torch.Tensor) and image.ndim == 4 and image.shape[0] > 0:
            items.append((index, "image", image))
    for index in range(1, videos + 1):
        video = kwargs.get(f"video_{index}")
        soundtrack = _plain_audio(kwargs.get(f"video_{index}_audio"))
        if video is None:
            continue
        if isinstance(video, torch.Tensor):
            if video.ndim != 4 or video.shape[0] < 1:
                raise ValueError(f"video_{index} 不是有效的 IMAGE 帧序列")
            video = {"images": video, "audio": soundtrack, "fps": IMAGE_SEQUENCE_FPS}
        elif hasattr(video, "get_components") and soundtrack is not None:
            components = video.get_components()
            video = {"images": components.images, "audio": soundtrack,
                     "fps": float(components.frame_rate or IMAGE_SEQUENCE_FPS)}
        items.append((images + index, "video", video))
    for index in range(1, audios + 1):
        audio = _plain_audio(kwargs.get(f"audio_{index}"))
        if audio is not None:
            items.append((images + videos + index, "audio", audio))
    return items


def _linked_keys(images: int, videos: int, audios: int) -> list:
    return list(_linked_input_types(images, videos, audios))


def _merge_linked(records: list, items: list) -> list:
    """Linked sockets replace the gallery record with the same type and number."""
    merged = list(records)
    for slot, media_type, value in items:
        ordinal = slot - SLOT_OFFSETS[media_type]
        merged = [record for record in merged
                  if not (record.get("media_type") == media_type and int(record.get("ordinal") or 0) == ordinal)]
        merged.append({"filename": "", "media_type": media_type, "ordinal": ordinal, "value": value, "audio_trim": ""})
    order = {"image": 0, "video": 1, "audio": 2}
    return sorted(merged, key=lambda record: (order.get(record.get("media_type"), 3), int(record.get("ordinal") or 0)))


class FeiHouEasyH3RHMedia:
    CATEGORY = "FeiHou Easy H3"
    FUNCTION = "media"
    RETURN_TYPES = (MEDIA_TYPE,)
    RETURN_NAMES = ("h3_media",)
    DESCRIPTION = (
        "RH 媒体载入：9 图 / 3 视频 / 3 音频，使用原有 RH 上传通道和 input 资源。接 Setup 的 h3_media。"
        "每类卡片左边可以外接连线，按接入顺序编号；外接的优先，覆盖同编号卡片。"
    )

    @classmethod
    def INPUT_TYPES(cls):
        # Same transport as the RH main node; no server-wide resource scan.
        optional = {}
        for index in range(1, MAX_MEDIA + 1):
            for name in (f"media_{index}", f"media_type_{index}", f"media_trim_{index}"):
                optional[name] = ("STRING", {"default": "", "hidden": True})
        optional["embedded_media_json"] = ("STRING", {"default": "", "multiline": True, "hidden": True})
        optional.update(_linked_input_types(MAX_IMAGES, MAX_VIDEOS, MAX_AUDIOS))
        return {"required": {}, "optional": optional,
                "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO"}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Reuse RH's file-aware fingerprint, so replacing media invalidates Setup.
        return FeiHouEasyH3.IS_CHANGED(**kwargs)

    @staticmethod
    def media(embedded_media_json="", extra_pnginfo=None, unique_id=None, **kwargs):
        items = _linked_items(kwargs, MAX_IMAGES, MAX_VIDEOS, MAX_AUDIOS)
        for key in _linked_keys(MAX_IMAGES, MAX_VIDEOS, MAX_AUDIOS):
            kwargs.pop(key, None)
        records = _media_records_from_inputs(
            {**kwargs, "embedded_media_json": embedded_media_json}, extra_pnginfo, unique_id)
        return ({"schema": 1, "source": "feihou_easy_h3_rh_media", "records": _merge_linked(records, items)},)


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
            # Linked media carry tensors: those records go through as a list, not JSON.
            linked = any(record.get("value") is not None for record in records)
            kwargs["embedded_media_json"] = records if linked else json.dumps(records, ensure_ascii=False)
        kwargs, continuation = prepare_setup(kwargs)
        model, second_model, context = super().generate(**kwargs)
        return model, second_model, apply_guide(context, continuation)


class FeiHouEasyH3RHContinuousOutput(FeiHouEasyH3ContinuousOutput):
    """Legacy RH packed-output unpacker, retained for saved class/type IDs."""
