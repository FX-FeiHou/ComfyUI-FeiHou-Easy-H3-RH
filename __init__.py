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
from .dual_sample import (
    FeiHouEasyH3DualSample1st,
    FeiHouEasyH3DualSample2nd,
    FeiHouEasyH3SampleEnhancer1st,
    FeiHouEasyH3SampleEnhancer2nd,
)
from .split_nodes import FeiHouEasyH3RHContinuousOutput, FeiHouEasyH3RHMedia, FeiHouEasyH3RHSetup
from .production_continuation import FeiHouEasyH3ContinueOut

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
    "FeiHouEasyH3RHDualSample1st": FeiHouEasyH3DualSample1st,
    "FeiHouEasyH3RHDualSample2nd": FeiHouEasyH3DualSample2nd,
    "FeiHouEasyH3RHSampleEnhancer1st": FeiHouEasyH3SampleEnhancer1st,
    "FeiHouEasyH3RHSampleEnhancer2nd": FeiHouEasyH3SampleEnhancer2nd,
    "FeiHouEasyH3RHMedia": FeiHouEasyH3RHMedia,
    "FeiHouEasyH3RHSetup": FeiHouEasyH3RHSetup,
    "FeiHouEasyH3RHContinuousOutput": FeiHouEasyH3RHContinuousOutput,
    "FeiHouEasyH3RHContinueOut": FeiHouEasyH3ContinueOut,
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
    "FeiHouEasyH3RHDualSample1st": "FeiHou Easy H3 Dual Sample 1st（一采）· RH",
    "FeiHouEasyH3RHDualSample2nd": "FeiHou Easy H3 Dual Sample 2nd（二采）· RH",
    "FeiHouEasyH3RHSampleEnhancer1st": "FeiHou Easy H3 1st Sample Enhancer（一采）· RH",
    "FeiHouEasyH3RHSampleEnhancer2nd": "FeiHou Easy H3 2nd Sample Enhancer（二采）· RH",
    "FeiHouEasyH3RHMedia": "FeiHou Easy H3 Media · RH",
    "FeiHouEasyH3RHSetup": "FeiHou Easy H3 Setup · RH",
    "FeiHouEasyH3RHContinuousOutput": "FeiHou Easy H3 Continuous 输出 · RH",
    "FeiHouEasyH3RHContinueOut": "FeiHou Easy H3 接续合并 · RH",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
