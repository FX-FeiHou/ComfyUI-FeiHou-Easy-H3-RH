from .nodes import (
    FeiHouEasyH3Resolution,
    FeiHouEasyH3,
    FeiHouEasyH3Loader,
    FeiHouEasyH3RemixLoader,
    FeiHouEasyH3ModelAdapter,
    FeiHouEasyH3LoraStack,
    FeiHouEasyH3Output,
    FeiHouEasyH3DurationCrop,
    FeiHouEasyH3PromptPreview,
)

from .face_refine import FeiHouEasyH3FaceRefine
from .production_pack import FeiHouEasyH3ProductionPackLoader

NODE_CLASS_MAPPINGS = {
    "FeiHouEasyH3RHFaceRefine": FeiHouEasyH3FaceRefine,
    "FeiHouEasyH3RHProductionPackLoader": FeiHouEasyH3ProductionPackLoader,
    "FeiHouEasyH3RHResolution": FeiHouEasyH3Resolution,
    "FeiHouEasyH3RHRemixLoader": FeiHouEasyH3RemixLoader,
    # RH has distinct Comfy class IDs so it can coexist with the standard edition.
    "FeiHouEasyH3RHLoraStack": FeiHouEasyH3LoraStack,
    "FeiHouEasyH3RHLoader": FeiHouEasyH3Loader,
    "FeiHouEasyH3RHModelAdapter": FeiHouEasyH3ModelAdapter,
    "FeiHouEasyH3RH": FeiHouEasyH3,
    "FeiHouEasyH3RHOutput": FeiHouEasyH3Output,
    "FeiHouEasyH3RHDurationCrop": FeiHouEasyH3DurationCrop,
    "FeiHouEasyH3RHPromptPreview": FeiHouEasyH3PromptPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FeiHouEasyH3RHFaceRefine": "FeiHou Easy H3 Face Refine (Experimental) · RH",
    "FeiHouEasyH3RHProductionPackLoader": "FeiHou Easy H3 Production Pack Loader · RH",
    "FeiHouEasyH3RHResolution": "FeiHou Easy H3 Resolution · RH",
    "FeiHouEasyH3RHRemixLoader": "FeiHou Easy H3 Remix加载器 · RH",
    "FeiHouEasyH3RHLoraStack": "加载LoRA（仅模型）· RH",
    "FeiHouEasyH3RHLoader": "FeiHou Easy H3 加载器 · RH",
    "FeiHouEasyH3RHModelAdapter": "FeiHou Easy H3 模型中转 · RH",
    "FeiHouEasyH3RH": "ComfyUI-FeiHou-Easy-H3-RH",
    "FeiHouEasyH3RHOutput": "FeiHou Easy H3 输出 · RH",
    "FeiHouEasyH3RHDurationCrop": "FeiHou Easy H3 数字人/MV 时长裁剪 · RH",
    "FeiHouEasyH3RHPromptPreview": "FeiHou Easy H3 提示词预览 · RH",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
