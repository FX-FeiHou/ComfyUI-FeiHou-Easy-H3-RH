"""FeiHou Easy H3 Shot Prompts: every motion-transfer shot from one markdown file.

The outside agent (``feihou-h3-motion`` skill) writes one ``.md`` file: a header
plus one block per shot.  Each block carries its reference-video time range, the
reference pictures it uses and the complete six-section prompt:

    ===== FEIHOU_SHOT 01 =====
    @range 00:00.00-00:03.08
    @pictures 1
    subject_definitions:
    ...

``@continue`` marks a block that starts from the end of the previous one (the
same shot was split at the 20 second limit); without it the block starts from
nothing, i.e. the reference video cuts there.

``@hold 26.5`` in the header (before the first block) puts the first frame of
reference video 1, held for that long and silent, in front of the timeline:
the talk-then-dance film talks over the held frame and the dance follows.
Every @range is measured on that longer timeline.

The node reuses the production-pack socket (``FEIHOU_H3_PRODUCTION_SHOT``), so
Setup accepts either loader on the same input and takes only the prompt and the
duration from it: the media still come from the Media Bridge.  A small state
file next to the saved videos remembers which block comes next, so an
interrupted run continues where it stopped instead of starting over.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from typing import Any

import folder_paths

from . import timed_prompt
from .production_pack import SHOT_TYPE


LOGGER = logging.getLogger(__name__)

FPS = 24.0
# A block is one saved video with no length limit: Motion Segment splits a
# long block (frame windows of segment_frames, or context windows), and @split
# segments are at most 15 s each.
MAX_SEGMENT_SECONDS = 15.0
# 原片直出 keeps the whole block in memory at the output size.
MAX_PASSTHROUGH_SECONDS = 20.0
MIN_BLOCK_SECONDS = 0.2
# @hold: the held first frame in front of reference video 1.
MAX_HOLD_SECONDS = 600.0
OUTPUT_SUBDIR = "feihou_h3_rh_motion"
STATE_VERSION = 1

START_AUTO = "自动续接"
START_RESTART = "从头开始"
START_MANUAL = "手动设置"

# ``===== FEIHOU_SHOT 03 =====`` (case-insensitive, at least one '=' on each side).
SENTINEL = re.compile(r"^=+\s*FEIHOU_SHOT\s+(\d+)\s*=+\s*$", re.IGNORECASE)
# ``@range 00:00.00-00:03.08`` / ``@pictures 1,3`` / ``@continue``.
DIRECTIVE = re.compile(r"^@([A-Za-z_一-鿿]+)(?:\s+(.*?))?\s*$")
# 「原片直出」: the block is not sampled, the source frames go straight to the film.
PASSTHROUGH_KEYS = {"passthrough", "原片", "原片直出", "直出"}
# @sound: which audio this block keeps in the film (overrides Motion Collect's audio_output).
SOUND_KEYS = {"sound", "声音", "音频输出"}
SOUND_VALUES = {"source": "source", "原声": "source", "原声音频": "source",
                "generated": "generated", "生成": "generated", "生成音频": "generated"}
TIME_SPLIT = re.compile(r"\s*[-–—~～至]\s*")
HOLD_KEYS = {"hold", "定格", "开头定格"}
# @video none: this block encodes no reference video (e.g. a talk block).
VIDEO_KEYS = {"video", "视频", "参考视频"}
VIDEO_OFF = {"none", "no", "off", "0", "false", "-", "无", "空", "不送", "不用", "关"}
# @audio 分块 (md header): every audio card follows each block's @range, so a talk
# block sends only its own seconds of the recording as <Audio N>.
AUDIO_WINDOW_KEYS = {"audio", "音频", "音频卡"}
AUDIO_WINDOW_ON = {"分块", "按分块", "跟随分镜", "跟随分块", "window", "slice", "range", "block", "blocks"}
# @first 4: picture card 4 is the block's first frame (keyframe at frame 0), so a
# block run on its own still starts from the right person when no previous tail exists.
FIRST_KEYS = {"first", "首帧", "首帧图"}
# @脸部模糊 3 / 自动 / 关 (H3 动作迁移预处理): this block's source-face blur level,
# over the preprocess node's own setting.
FACE_BLUR_KEYS = {"脸部模糊", "模糊", "blur", "face_blur", "faceblur"}
# @分段 上下文窗口 192 34 30秒 / 帧窗口 124 22 / 不分段 (header = every block, a block
# overrides it): how Motion Segment samples the block when its 分段方式 is 自动.
SEGMENTATION_KEYS = {"分段", "分段方式", "segmentation", "segment"}
SEG_WHOLE, SEG_CHAIN, SEG_CONTEXT = "不分段", "帧窗口", "上下文窗口"
SEG_ALIASES = {"不分段": SEG_WHOLE, "整段": SEG_WHOLE, "关闭": SEG_WHOLE, "关": SEG_WHOLE, "whole": SEG_WHOLE, "off": SEG_WHOLE,
               "帧窗口": SEG_CHAIN, "接续": SEG_CHAIN, "chain": SEG_CHAIN,
               "上下文窗口": SEG_CONTEXT, "上下文": SEG_CONTEXT, "context": SEG_CONTEXT}
# Same ranges as Motion Segment's option lists; values left out use its recommended ones.
SEG_SPECS = {
    SEG_CHAIN: {"frames": (39, 497), "overlaps": ("22", "39", "5"), "default": (124, "22")},
    SEG_CONTEXT: {"frames": (124, 362), "overlaps": ("22", "39", "56", "73", "90", "107"), "default": (345, "73")},
}
# Context-window overlaps are 5 + 17k frames; older mds wrote 34 / 68 / 102 for 39 / 73 / 107
# (same table as h3_context_windows.LEGACY_OVERLAPS).
LEGACY_CONTEXT_OVERLAPS = {"34": "39", "68": "73", "102": "107"}
CONTEXT_SEGMENT_SECONDS = (20, 30, 45, 60)
CONTEXT_SEGMENT_WHOLE = "整块一次"


@dataclass(frozen=True)
class Shot:
    """One block of the markdown: a time range, its pictures and its prompt."""

    index: int
    start: float
    end: float
    prompt: str
    pictures: tuple[int, ...] = ()
    pictures_explicit: bool = False
    continues: bool = False
    passthrough: bool = False
    # @split: where the block's in-block segments change (timeline seconds).
    splits: tuple[float, ...] = ()
    # @sound: "source" / "generated", or "" to follow Motion Collect's audio_output.
    sound: str = ""
    # @hold (md header): seconds of held first frame in front of reference video 1.
    hold: float = 0.0
    # @video none: False = the block's prompt is encoded without the reference videos.
    video: bool = True
    # @first N: picture card N anchors the block's first frame (0 = none).
    first_picture: int = 0
    # @audio 分块 (md header): audio cards are cut to this block's @range.
    audio_window: bool = False
    # @脸部模糊: "" = not written (the preprocess node decides), "off", "auto" or "1"-"5".
    face_blur: str = ""
    # @分段 (this block, else the md header): None = not written.
    segmentation: tuple = ()

    @property
    def seconds(self) -> float:
        return round(self.end - self.start, 3)

    @property
    def start_frame(self) -> int:
        return int(round(self.start * FPS))

    @property
    def end_frame(self) -> int:
        return int(round(self.end * FPS))

    @property
    def hold_frames(self) -> int:
        return int(round(self.hold * FPS))

    @property
    def frames(self) -> int:
        # Round both edges against the absolute timeline, so the blocks tile it
        # exactly instead of drifting one frame per boundary.
        return max(1, self.end_frame - self.start_frame)


def _splits(value: str, start: float, end: float, where: str) -> tuple[float, ...]:
    """@split 00:12.40, 00:26.00 — in-block segment boundaries on the timeline.

    Each segment between them (and the block edges) is at most 15 s.  The
    skill puts them where the framing changes inside a continuous shot.
    """
    text = str(value or "").strip()
    if not text:
        return ()
    points = []
    for part in re.split(r"[,，;；\s]+", text):
        if part:
            points.append(time_seconds(part))
    edges = [start, *points, end]
    if any(right <= left + 0.5 for left, right in zip(edges, edges[1:])):
        raise ValueError(f"{where} 的 @split 必须落在 @range 之内、从早到晚，每段至少 0.5 秒：{text}")
    for left, right in zip(edges, edges[1:]):
        if right - left > MAX_SEGMENT_SECONDS + 1e-6:
            raise ValueError(f"{where} 的 @split 分出的块内分镜 {time_text(left)}-{time_text(right)} "
                             f"有 {right - left:.2f} 秒，超过 {MAX_SEGMENT_SECONDS:.0f} 秒")
    return tuple(points)


def time_seconds(value: Any) -> float:
    """Parse ``83`` / ``01:23.4`` / ``00:01:23.400`` into seconds."""
    text = str(value or "").strip().replace("：", ":").replace("．", ".").replace("，", ".")
    if not text:
        raise ValueError("时间不能为空")
    parts = text.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except (TypeError, ValueError):
        pass
    raise ValueError(f"无法识别的时间：{value!r}（可写 12.5、01:12.5 或 00:01:12.500）")


def time_text(seconds: float) -> str:
    total = max(0.0, float(seconds))
    minutes, rest = divmod(total, 60)
    return f"{int(minutes):02d}:{rest:06.3f}"


def fingerprint(text: str) -> str:
    """Identity of this markdown: a changed file never resumes an old run."""
    return hashlib.sha256(str(text or "").replace("\r\n", "\n").encode("utf-8")).hexdigest()


# H3 only understands the English tags; a Chinese-written prompt sometimes keeps
# "@图片1" or "<视频 2>" in the body, so normalise them (with a warning).
TAG_ALIASES = (
    (re.compile(r"@\s*(?:图片|图像|Picture|Image)\s*(\d+)", re.IGNORECASE), r"<Picture \1>"),
    (re.compile(r"@\s*(?:视频|Video)\s*(\d+)", re.IGNORECASE), r"<Video \1>"),
    (re.compile(r"@\s*(?:音频|音乐|Audio)\s*(\d+)", re.IGNORECASE), r"<Audio \1>"),
    (re.compile(r"<\s*(?:图片|图像)\s*(\d+)\s*>"), r"<Picture \1>"),
    (re.compile(r"<\s*视频\s*(\d+)\s*>"), r"<Video \1>"),
    (re.compile(r"<\s*音频\s*(\d+)\s*>"), r"<Audio \1>"),
)


def normalize_prompt_tags(prompt: str, shot_index: int = 0) -> str:
    """Rewrite @图片1 / <视频 2> style references to the official H3 tags."""
    text = str(prompt or "")
    total = 0
    for pattern, replacement in TAG_ALIASES:
        text, count = pattern.subn(replacement, text)
        total += count
    if total:
        LOGGER.warning(
            "Easy H3 shot prompts: 分镜 %s 的提示词里有 %d 处非英文引用（@图片1 / <视频 2> 之类），"
            "已自动改写成 <Picture N> / <Video N> / <Audio N>；skills 应当直接写英文标签。",
            shot_index or "?", total)
    return text


def _split_directives(body: list[tuple[int, str]], sentinel_line: int) -> tuple[dict[str, str], str]:
    """Split a block into its leading ``@`` directives and the prompt body."""
    directives: dict[str, str] = {}
    start = 0
    for offset, (line_number, line) in enumerate(body):
        text = line.strip()
        if not text:
            start = offset + 1
            continue
        match = DIRECTIVE.match(text)
        if not match:
            break
        directives[match.group(1).lower()] = (match.group(2) or "").strip()
        start = offset + 1
    prompt = "\n".join(line for _number, line in body[start:]).strip()
    if not directives:
        raise ValueError(f"第 {sentinel_line} 行：这个分镜块缺少 @range，无法知道取参考视频的哪一段")
    return directives, prompt


def _pictures(value: str, line_hint: str) -> tuple[int, ...]:
    if not value:
        return ()
    if value.strip().lower() in {"none", "no", "-", "无", "空"}:
        # A crowd / empty / prop block: send no character picture at all.
        return ()
    numbers = []
    for token in re.split(r"[\s,;，、]+", value.strip()):
        if not token:
            continue
        try:
            number = int(token)
        except ValueError:
            raise ValueError(f"{line_hint}：@pictures 只能是数字，无法识别 {token!r}")
        if not 1 <= number <= 9:
            raise ValueError(f"{line_hint}：@pictures 只能是 1–9 的参考图编号，得到 {number}")
        if number not in numbers:
            numbers.append(number)
    return tuple(numbers)


# @分段 fields, written 名字=值 (Chinese or English names, any order).
SEG_FIELD_NAMES = {
    "窗口": "window", "window": "window",
    "段长": "length", "每段帧数": "length", "length": "length",
    "重叠": "overlap", "overlap": "overlap",
    "每段": "segment", "每段上限": "segment", "segment": "segment",
}
SEG_FIELDS = {SEG_CHAIN: ("length", "overlap"), SEG_CONTEXT: ("window", "overlap", "segment")}
SEG_USAGE = "例如 @分段 上下文窗口 窗口=192 重叠=39 每段=30秒、@分段 帧窗口 段长=124 重叠=22 或 @分段 不分段"


def _seg_number(text: str, unit: str) -> str:
    return text.strip().lower().removesuffix(unit).removesuffix("s").strip()


def _segmentation_value(value: str, where: str) -> dict:
    """@分段 上下文窗口 窗口=192 重叠=39 每段=30秒 → {"mode", "segment_frames", "overlap_frames", "context_segment"}.

    Fields left out take Motion Segment's recommended values.  Bare numbers in
    the field order (窗口 重叠 每段 / 段长 重叠) are still read.
    """
    parts = [part for part in re.split(r"[\s,，;；]+", str(value or "").strip()) if part]
    if not parts or parts[0].lower() not in SEG_ALIASES:
        raise ValueError(f"{where}：@分段 要先写 不分段、帧窗口 或 上下文窗口（{SEG_USAGE}），实际是「{value}」")
    mode = SEG_ALIASES[parts[0].lower()]
    rest = parts[1:]
    if mode == SEG_WHOLE:
        if rest:
            raise ValueError(f"{where}：@分段 不分段 后面不用写参数，实际是「{value}」")
        return {"mode": mode}
    allowed = SEG_FIELDS[mode]
    fields: dict = {}
    positional = []
    for part in rest:
        name, sep, raw = part.replace("＝", "=").replace("：", "=").replace(":", "=").partition("=")
        if not sep:
            positional.append(part)
            continue
        key = SEG_FIELD_NAMES.get(name.strip().lower())
        if key not in allowed:
            names = "、".join(n for n, k in SEG_FIELD_NAMES.items() if k in allowed and not n.isascii())
            raise ValueError(f"{where}：@分段 {mode} 没有「{name}」这个参数，只能写 {names}（{SEG_USAGE}）")
        if key in fields:
            raise ValueError(f"{where}：@分段 的「{name}」写了两次")
        fields[key] = raw
    if positional:
        if fields:
            raise ValueError(f"{where}：@分段 不能把 名字=值 和不带名字的数字混着写（{SEG_USAGE}）")
        if len(positional) > len(allowed):
            raise ValueError(f"{where}：@分段 {mode} 的参数太多（{SEG_USAGE}），实际是「{value}」")
        fields = dict(zip(allowed, positional))
    spec = SEG_SPECS[mode]
    frames_key = "window" if mode == SEG_CONTEXT else "length"
    frames_text = _seg_number(fields.get(frames_key, str(spec["default"][0])), "帧")
    overlap = _seg_number(fields.get("overlap", spec["default"][1]), "帧")
    if not frames_text.isdigit():
        raise ValueError(f"{where}：@分段 的帧数要写数字，实际是「{fields.get(frames_key)}」")
    frames = int(frames_text)
    low, high = spec["frames"]
    if not low <= frames <= high or (frames - 5) % 17:
        raise ValueError(f"{where}：@分段 {mode} 的帧数要是 5+17N、在 {low}–{high} 之间（如 124、192、345），实际是 {frames}")
    if mode == SEG_CONTEXT:
        overlap = LEGACY_CONTEXT_OVERLAPS.get(overlap, overlap)  # 34 / 68 / 102 from older mds
    if overlap not in spec["overlaps"]:
        raise ValueError(f"{where}：@分段 {mode} 的重叠只能是 {' / '.join(spec['overlaps'])} 帧，实际是 {overlap}")
    result = {"mode": mode, "segment_frames": str(frames), "overlap_frames": overlap}
    if mode == SEG_CONTEXT:
        segment = _seg_number(fields.get("segment", "30"), "秒")
        if segment in {CONTEXT_SEGMENT_WHOLE, "整块"}:
            result["context_segment"] = CONTEXT_SEGMENT_WHOLE
        elif segment.isdigit() and int(segment) in CONTEXT_SEGMENT_SECONDS:
            result["context_segment"] = f"{int(segment)} 秒"
        else:
            raise ValueError(f"{where}：@分段 上下文窗口 的每段只能是 "
                             f"{' / '.join(f'{s}秒' for s in CONTEXT_SEGMENT_SECONDS)} 或 整块，实际是「{fields.get('segment')}」")
    return result


def _face_blur(value: str, where: str) -> str:
    """@脸部模糊 3 / 3档 / 自动 / 关 → "1"-"5", "auto" or "off"."""
    text = str(value or "").strip().lower().replace("档", "").replace("级", "")
    if text in {"0", "关", "off", "none", "no", "false", "不模糊", "无"}:
        return "off"
    if text in {"自动", "auto"}:
        return "auto"
    if text.isdigit() and 1 <= int(text) <= 5:
        return text
    raise ValueError(f"{where}：@脸部模糊 只能写 关、自动 或 1–5 档，例如 @脸部模糊 5，实际是「{value}」")


def _flag(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    return text not in {"0", "false", "no", "off", "否", "不", "硬切", "不用"}


def parse_shot_prompts(text: str) -> list[Shot]:
    """Parse the markdown into shots; every problem names the line that caused it."""
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[tuple[int, list[tuple[int, str]], int]] = []
    current: list[tuple[int, str]] | None = None
    hold = 0.0
    audio_window = False
    header_segmentation = ()
    for number, line in enumerate(lines, 1):
        match = SENTINEL.match(line.strip())
        if match:
            current = []
            blocks.append((int(match.group(1)), current, number))
            continue
        if current is not None:
            current.append((number, line))
            continue
        header = DIRECTIVE.match(line.strip())
        if header and header.group(1).lower() in SEGMENTATION_KEYS:
            header_segmentation = tuple(_segmentation_value(header.group(2), f"第 {number} 行").items())
        elif header and header.group(1).lower() in HOLD_KEYS:
            hold = _hold_seconds(header.group(2), number)
        elif header and header.group(1).lower() in AUDIO_WINDOW_KEYS:
            value = str(header.group(2) or "").strip().lower()
            if value not in AUDIO_WINDOW_ON:
                raise ValueError(f"第 {number} 行：@audio 只能写 分块（音频卡按每块的 @range 截取），实际是「{header.group(2) or ''}」")
            audio_window = True
    if not blocks:
        raise ValueError(
            "没有找到分镜分隔行。请用 skills 生成的 md，每个分镜以「===== FEIHOU_SHOT 01 =====」开头。")

    shots: list[Shot] = []
    expected = 1
    previous_end = 0.0
    for index, body, sentinel_line in blocks:
        if index != expected:
            raise ValueError(f"第 {sentinel_line} 行：分镜序号应为 {expected}，实际是 {index}（序号必须从 1 连续递增）")
        directives, prompt = _split_directives(body, sentinel_line)
        passthrough = any(_flag(directives[key]) for key in PASSTHROUGH_KEYS if key in directives)
        if not prompt and not passthrough:
            raise ValueError(f"第 {sentinel_line} 行：分镜 {index} 没有提示词正文（不需要采样的块写 @passthrough）")
        if "range" not in directives:
            raise ValueError(f"第 {sentinel_line} 行：分镜 {index} 缺少 @range 起-止")
        parts = TIME_SPLIT.split(directives["range"].strip())
        if len(parts) != 2:
            raise ValueError(f"第 {sentinel_line} 行：@range 必须写成「起-止」，例如 00:03.08-00:07.21")
        start, end = time_seconds(parts[0]), time_seconds(parts[1])
        seconds = round(end - start, 3)
        if seconds <= 0:
            raise ValueError(f"第 {sentinel_line} 行：分镜 {index} 的 @range 结束时间必须大于开始时间")
        if seconds < MIN_BLOCK_SECONDS:
            raise ValueError(f"第 {sentinel_line} 行：分镜 {index} 只有 {seconds:.2f} 秒，太短")
        if passthrough and seconds > MAX_PASSTHROUGH_SECONDS + 1e-6:
            raise ValueError(
                f"第 {sentinel_line} 行：原片直出的分镜 {index} 有 {seconds:.2f} 秒，超过 {MAX_PASSTHROUGH_SECONDS:.0f} 秒；"
                f"请拆成 {math.ceil(seconds / MAX_PASSTHROUGH_SECONDS)} 个 @passthrough 分镜")
        if start < -1e-6:
            raise ValueError(f"第 {sentinel_line} 行：分镜 {index} 的开始时间不能是负数")
        if start < previous_end - 1e-3:
            raise ValueError(
                f"第 {sentinel_line} 行：分镜 {index} 从 {time_text(start)} 开始，早于上一个分镜的结束 {time_text(previous_end)}（时间轴不能重叠）")
        continues = _flag(directives.get("continue", "0"))
        if continues and not shots:
            LOGGER.warning("Easy H3 shot prompts: 第 %d 行的 @continue 没有上一块，已忽略", sentinel_line)
            continues = False
        pictures = _pictures(directives.get("pictures", ""), f"第 {sentinel_line} 行")
        pictures_explicit = "pictures" in directives
        splits = _splits(directives.get("split", ""), start, end, f"第 {sentinel_line} 行：分镜 {index}")
        if not splits and not passthrough and seconds > MAX_SEGMENT_SECONDS + 1e-6:
            LOGGER.info("Easy H3 shot prompts: 分镜 %d 有 %.2f 秒、没写 @split，按「动作迁移分段」的帧窗口设置分段",
                        index, seconds)
        sound = ""
        for key in SOUND_KEYS & set(directives):
            value = str(directives[key] or "").strip().lower()
            if value not in SOUND_VALUES:
                raise ValueError(f"第 {sentinel_line} 行：@sound 只能写 原声 或 生成（source / generated），实际是「{directives[key]}」")
            sound = SOUND_VALUES[value]
        video = True
        for key in VIDEO_KEYS & set(directives):
            value = str(directives[key] or "").strip().lower()
            if value not in VIDEO_OFF:
                raise ValueError(f"第 {sentinel_line} 行：@video 只能写 none（本块不送参考视频），实际是「{directives[key]}」")
            video = False
        first_picture = 0
        for key in FIRST_KEYS & set(directives):
            value = str(directives[key] or "").strip()
            if not value.isdigit() or not 1 <= int(value) <= 9:
                raise ValueError(f"第 {sentinel_line} 行：@first 要写首帧图的图卡编号 1–9，例如 @first 4，实际是「{directives[key]}」")
            first_picture = int(value)
        face_blur = ""
        for key in FACE_BLUR_KEYS & set(directives):
            face_blur = _face_blur(directives[key], f"第 {sentinel_line} 行")
        segmentation = header_segmentation or ()
        for key in SEGMENTATION_KEYS & set(directives):
            segmentation = tuple(_segmentation_value(directives[key], f"第 {sentinel_line} 行：分镜 {index}").items())
        unknown = (set(directives) - {"range", "pictures", "continue", "split"} - PASSTHROUGH_KEYS - SOUND_KEYS
                   - VIDEO_KEYS - FIRST_KEYS - FACE_BLUR_KEYS - SEGMENTATION_KEYS)
        if unknown:
            LOGGER.warning("Easy H3 shot prompts: 第 %d 行忽略未知字段 %s", sentinel_line, ", ".join(sorted(unknown)))
        shots.append(Shot(index=index, start=start, end=end, prompt=normalize_prompt_tags(prompt, index),
                          pictures=pictures, pictures_explicit=pictures_explicit, continues=continues,
                          passthrough=passthrough, splits=splits, sound=sound, hold=hold, video=video,
                          first_picture=first_picture, audio_window=audio_window, face_blur=face_blur,
                          segmentation=segmentation))
        previous_end = end
        expected += 1
    LOGGER.info("Easy H3 shot prompts: %d 个分镜，共 %.2f 秒%s%s", len(shots), sum(shot.seconds for shot in shots),
                f"（参考视频 1 前面定格首帧 {hold:.2f} 秒）" if hold else "",
                "，音频卡按每块 @range 截取" if audio_window else "")
    return shots


def _hold_seconds(value: str, line_number: int) -> float:
    """@hold 26.5 / @hold 00:26.500 in the md header."""
    try:
        seconds = time_seconds(value)
    except ValueError:
        raise ValueError(f"第 {line_number} 行：@hold 要写定格秒数，例如 @hold 26.5，实际是「{value or ''}」")
    if not 0 <= seconds <= MAX_HOLD_SECONDS:
        raise ValueError(f"第 {line_number} 行：@hold 必须在 0～{MAX_HOLD_SECONDS:.0f} 秒之间，实际是 {seconds:g} 秒")
    return seconds


MARKDOWN_SUFFIXES = (".md", ".markdown", ".txt")
MAX_MARKDOWN_BYTES = 4 * 1024 * 1024

# A browser page never learns a file's real path, so 「选择 md 文件」 asks the
# server (the same machine) to show the native dialog; the path then lives in
# md_path and survives reloads and restarts.  tkinter runs in a child process so
# its event loop never touches the server thread.
_PICKER_SCRIPT = r"""
import sys, tkinter
from tkinter import filedialog
root = tkinter.Tk()
root.withdraw()
root.attributes("-topmost", True)
path = filedialog.askopenfilename(parent=root, title="选择分镜 md", initialdir=sys.argv[1] or None,
                                  filetypes=[("分镜 md", "*.md *.markdown *.txt"), ("所有文件", "*.*")])
root.destroy()
sys.stdout.write(path or "")
"""


def markdown_path(value: Any) -> str:
    raw = os.path.expandvars(os.path.expanduser(str(value or "").strip().strip('"').strip("'")))
    return os.path.normpath(os.path.abspath(raw)) if raw else ""


def read_markdown_file(value: Any) -> dict[str, Any]:
    path = markdown_path(value)
    if not path:
        raise ValueError("md_path 是空的。")
    if not path.lower().endswith(MARKDOWN_SUFFIXES):
        raise ValueError(f"只能读取 .md / .markdown / .txt 文件：{path}")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"找不到 md 文件（被移动或改名了？）：{path}")
    size = os.path.getsize(path)
    if size > MAX_MARKDOWN_BYTES:
        raise ValueError(f"md 文件超过 4 MB：{path}")
    with open(path, "r", encoding="utf-8-sig") as handle:
        text = handle.read()
    return {"path": path, "name": os.path.basename(path), "text": text, "mtime": os.path.getmtime(path)}


def pick_markdown_path(initial: Any = "") -> str:
    import subprocess
    import sys

    folder = os.path.dirname(markdown_path(initial)) if initial else ""
    environment = dict(os.environ, PYTHONIOENCODING="utf-8")
    process = subprocess.run([sys.executable, "-c", _PICKER_SCRIPT, folder if os.path.isdir(folder) else ""],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=1800, env=environment)
    if process.returncode != 0:
        raise RuntimeError("打开文件选择框失败：" + (process.stderr or "").strip()[-400:])
    return markdown_path(process.stdout) if process.stdout.strip() else ""


def remote_markdown_roots() -> list[str]:
    """Folders a remote browser may read md from: ComfyUI's input and user folders."""
    return [os.path.realpath(folder) for folder in (folder_paths.get_input_directory(),
                                                    folder_paths.get_user_directory())]


def check_remote_markdown_path(value: Any) -> str:
    raw = str(value or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("md_path 是空的。")
    # Relative names belong to ComfyUI/input, never the server's working folder.
    raw = os.path.expanduser(raw)
    path = os.path.realpath(raw if os.path.isabs(raw) else os.path.join(folder_paths.get_input_directory(), raw))
    for root in remote_markdown_roots():
        try:
            if os.path.commonpath([root, path]) == root:
                return path
        except ValueError:  # another drive
            continue
    raise PermissionError("云端只能读取 ComfyUI 的 input 或 user 文件夹里的 md："
                          "把 md 上传到 input 后在 md_path 填文件名，或直接把内容粘贴进 prompt_text。")


def register_routes(routes, is_local, remote_enabled=lambda: False):
    from aiohttp import web
    import asyncio

    def refuse(request, remote_ok=False):
        if not is_local(request) and not (remote_ok and remote_enabled()):
            # local: False makes the node fall back to the browser's own file picker.
            return web.json_response({"ok": False, "local": False,
                                      "error": "只有在运行 ComfyUI 的这台电脑上才能按路径读 md。"}, status=403)
        # A custom header cannot be sent cross-site without a CORS preflight.
        if request.headers.get("X-FeiHou-Shot-Md") != "1":
            return web.json_response({"ok": False, "error": "请从 Easy H3 分镜节点操作。"}, status=403)
        return None

    @routes.post("/feihou_easy_h3/shot_md/pick")
    async def _pick_shot_markdown(request):
        # The dialog opens on the server's screen, so a remote browser always picks locally.
        refused = refuse(request)
        if refused is not None:
            return refused
        try:
            payload = await request.json() if request.can_read_body else {}
            path = await asyncio.to_thread(pick_markdown_path, (payload or {}).get("initial", ""))
            if not path:
                return web.json_response({"ok": True, "cancelled": True})
            return web.json_response({"ok": True, **await asyncio.to_thread(read_markdown_file, path)})
        except Exception as exc:  # reported in the browser, the node keeps its prompt
            LOGGER.warning("Easy H3 shot prompts: 选择 md 失败：%s", exc)
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @routes.post("/feihou_easy_h3/shot_md/read")
    async def _read_shot_markdown(request):
        refused = refuse(request, remote_ok=True)
        if refused is not None:
            return refused
        try:
            payload = await request.json()
            path = payload.get("path")
            if not is_local(request):
                try:
                    path = check_remote_markdown_path(path)
                except PermissionError as exc:
                    return web.json_response({"ok": False, "error": str(exc)}, status=403)
            return web.json_response({"ok": True, **await asyncio.to_thread(read_markdown_file, path)})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)


def output_root() -> str:
    """Run bookkeeping (resume states, block tails, V2 join manifests).

    Kept under ComfyUI/input, not the output folder: output folders are often
    synced (Syncthing, cloud drives) and a sync client briefly locking or
    replacing the state file made a running film restart as a new series.
    """
    return os.path.join(folder_paths.get_input_directory(), OUTPUT_SUBDIR)


STATE_RETRIES = 5
STATE_RETRY_SECONDS = 0.2


def _retry(action):
    """Run a state-file read/replace, retrying while the file is briefly locked."""
    for attempt in range(STATE_RETRIES):
        try:
            return action()
        except (PermissionError, json.JSONDecodeError):
            if attempt == STATE_RETRIES - 1:
                raise
            time.sleep(STATE_RETRY_SECONDS)


def state_path(markdown_fingerprint: str) -> str:
    return os.path.join(output_root(), f"{markdown_fingerprint[:16]}.state.json")


def series_directory(series: str) -> str:
    return os.path.join(output_root(), str(series))


_SERIES_NAMES: set[str] = set()


# feihou_h3_motion holds run bookkeeping only: resume states, per-series block
# tails and V2 join manifests.  Anything of ours older than this goes when a new
# series starts; per-segment preview videos (segment_*.mp4) are never touched.
PRUNE_SECONDS = 48 * 3600
_SERIES_NAME = re.compile(r"\d{8}_\d{6}(?:_[0-9a-f]{6})?(?:_\d+)?")
_STATE_NAME = re.compile(r"[0-9a-f]{16}\.state\.json")


def _finished_manifest(path: str) -> bool:
    """V2 has every block of this film, so it has already joined it."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        total = int(data.get("total") or 0)
        shots = data.get("shots") or {}
    except (OSError, ValueError, TypeError, AttributeError):
        return False
    return total > 0 and all(str(index) in shots for index in range(1, total + 1))


def prune_outputs(keep: str = "") -> int:
    """Remove stale run files from feihou_h3_motion; returns how many entries went.

    Finished manifests go at once (a finished film never runs again: the next
    run is a new series); everything else of ours after PRUNE_SECONDS.
    """
    root = output_root()
    try:
        entries = list(os.scandir(root))
    except OSError:
        return 0
    cutoff = time.time() - PRUNE_SECONDS
    removed = 0
    for entry in entries:
        name = entry.name
        if keep and (name == keep or name.startswith(keep + ".")):
            continue
        try:
            stale = entry.stat().st_mtime < cutoff
            if entry.is_dir():
                if _SERIES_NAME.fullmatch(name) and stale:
                    shutil.rmtree(entry.path, ignore_errors=True)
                    removed += 1
                continue
            stem = name.split(".", 1)[0]
            if _STATE_NAME.fullmatch(name) or (_SERIES_NAME.fullmatch(stem) and name.endswith(".tmp")):
                drop = stale
            elif _SERIES_NAME.fullmatch(stem) and name == stem + ".json":
                drop = stale or _finished_manifest(entry.path)
            else:
                continue
            if drop:
                os.remove(entry.path)
                if _STATE_NAME.fullmatch(name):
                    _forget_state(file_prefix=name[:16])
                removed += 1
        except OSError as exc:
            LOGGER.warning("Easy H3 shot prompts: 清理 %s 失败：%s", entry.path, exc)
    if removed:
        LOGGER.info("Easy H3 shot prompts: 清理了 %s 里 %d 个旧的进度 / 尾帧 / 拼接清单", root, removed)
    return removed


def finish_series(series: str, markdown_fingerprint: str) -> None:
    """The run is over: its block tails and its resume state are no longer needed.

    The manifest stays: Video Combine V2 joins the film from it right after
    this; the next series' prune_outputs removes it.
    """
    if series and os.path.basename(series) == series and series not in (".", ".."):
        shutil.rmtree(series_directory(series), ignore_errors=True)
    state = read_state(markdown_fingerprint)
    if state is not None and state.get("done"):
        _forget_state(markdown_fingerprint)
        try:
            os.remove(state_path(markdown_fingerprint))
        except OSError:
            pass


def new_series(markdown_fingerprint: str = "") -> str:
    """A fresh run name: two films must never share one series folder."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = f"{stamp}_{markdown_fingerprint[:6]}" if markdown_fingerprint else stamp
    candidate, counter = base, 1
    while (candidate in _SERIES_NAMES
           or os.path.isdir(series_directory(candidate))
           or os.path.exists(os.path.join(output_root(), f"{candidate}.json"))):
        counter += 1
        candidate = f"{base}_{counter}"
    _SERIES_NAMES.add(candidate)
    prune_outputs(keep=candidate)
    return candidate


# The last state written for each md in this ComfyUI session.  When the state
# file is gone mid-run (deleted by hand, or by a sync client), the run resumes
# from here instead of starting a new series; after a restart only the file counts.
_MEMORY_STATES: dict[str, dict[str, Any]] = {}


def _forget_state(markdown_fingerprint: str = "", file_prefix: str = "") -> None:
    for key in [key for key in _MEMORY_STATES
                if key == markdown_fingerprint or (file_prefix and key[:16] == file_prefix)]:
        _MEMORY_STATES.pop(key, None)


def read_state(markdown_fingerprint: str) -> dict[str, Any] | None:
    path = state_path(markdown_fingerprint)

    def read():
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    try:
        data = _retry(read)
    except (OSError, json.JSONDecodeError) as exc:
        remembered = _MEMORY_STATES.get(markdown_fingerprint)
        if remembered is None:
            if not isinstance(exc, FileNotFoundError):
                LOGGER.warning("Easy H3 shot prompts: 读不到续跑进度 %s（%s），按没有进度处理", path, exc)
            return None
        LOGGER.warning("Easy H3 shot prompts: 续跑进度文件%s，改用内存里的进度（分镜 %s，series %s）并重新写回",
                       "不见了" if isinstance(exc, FileNotFoundError) else f"读不到（{exc}）",
                       remembered.get("block"), remembered.get("series"))
        try:
            write_state(markdown_fingerprint, remembered)
        except OSError as error:
            LOGGER.warning("Easy H3 shot prompts: 写回续跑进度失败：%s", error)
        return dict(remembered)
    if not isinstance(data, dict) or data.get("fingerprint") != markdown_fingerprint:
        return None
    return data


def write_state(markdown_fingerprint: str, data: dict[str, Any]) -> None:
    path = state_path(markdown_fingerprint)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = dict(data, version=STATE_VERSION, fingerprint=markdown_fingerprint, updated=time.time())
    _MEMORY_STATES[markdown_fingerprint] = dict(payload)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    _retry(lambda: os.replace(temporary, path))


def parse_picks(value: str, total: int) -> list[int]:
    """Parse a block filter such as ``6,9`` or ``3-5`` (empty or ``0`` = every block)."""
    text = str(value or "").strip()
    if not text or re.fullmatch(r"0+", text):
        return []
    picks: set[int] = set()
    for chunk in re.split(r"[,，;；\s]+", text):
        if not chunk:
            continue
        match = re.fullmatch(r"(\d+)\s*[-~]\s*(\d+)", chunk)
        if match:
            low, high = int(match.group(1)), int(match.group(2))
            picks.update(range(min(low, high), max(low, high) + 1))
            continue
        if chunk.isdigit():
            picks.add(int(chunk))
            continue
        raise ValueError(f"分镜选择只接受块号，例如 6,9 或 3-5，收到 {chunk!r}")
    if not picks:
        return []
    bad = sorted(number for number in picks if number < 1 or number > total)
    if bad:
        raise ValueError(f"分镜选择里有不存在的块号 {bad}（这份 md 一共 {total} 块）")
    return sorted(picks)


def advance_block(markdown_fingerprint: str) -> dict[str, Any] | None:
    """Move to the next block after one finished; returns the new state."""
    state = read_state(markdown_fingerprint)
    if state is None:
        return None
    total = int(state.get("total") or 0)
    block = int(state.get("block") or 1) + 1
    picks = [int(item) for item in (state.get("picks") or [])]
    if picks:
        remaining = [item for item in picks if item >= block]
        block = remaining[0] if remaining else total + 1
        state.update(block=block, done=not remaining)
    else:
        state.update(block=block, done=total > 0 and block > total)
    write_state(markdown_fingerprint, state)
    return state


def finish_standalone_block(markdown_fingerprint: str, block: int) -> dict[str, Any]:
    """A Sample Enhancer run of ``block`` finished: advance 镜号 like Motion Collect does."""
    if not re.fullmatch(r"[0-9a-f]{8,64}", markdown_fingerprint or ""):
        raise ValueError("分镜提示词：无效的 md 指纹")
    state = read_state(markdown_fingerprint)
    if state is None or state.get("done"):
        return {"done": True, "next": None}
    if block and int(state.get("block") or 0) != int(block):
        # Already advanced (e.g. a second browser tab reported the same run).
        return {"done": False, "next": int(state.get("block") or 1), "stale": True}
    progress = advance_block(markdown_fingerprint) or {}
    done = bool(progress.get("done"))
    if done:
        finish_series(str(progress.get("series") or ""), markdown_fingerprint)
    LOGGER.info("Easy H3 shot prompts: 分镜 %d 完成（采样增强工作流），%s", block,
                "全片完成" if done else f"下一块 {progress.get('block')}")
    return {"done": done, "next": None if done else int(progress.get("block") or 0)}


# Sample Enhancer runs of 分镜提示词 in flight: prompt_id -> the block it was given.
_STANDALONE_RUNS: dict[str, dict[str, Any]] = {}


def _remember_standalone_run(unique_id: Any, markdown_fingerprint: str, block: int, start: str) -> None:
    """Note the running prompt's block; the queue hook finishes it when the run ends."""
    try:
        from server import PromptServer
    except ImportError:
        return
    server = getattr(PromptServer, "instance", None)
    prompt_id = getattr(server, "last_prompt_id", None)
    if not prompt_id or not install_queue_hook(getattr(server, "prompt_queue", None)):
        return
    _STANDALONE_RUNS[str(prompt_id)] = {"fingerprint": markdown_fingerprint, "block": int(block),
                                        "node": str(unique_id) if unique_id is not None else None,
                                        "start": str(start)}


def install_queue_hook(queue: Any) -> bool:
    """Wrap ``PromptQueue.task_done`` once so a finished block queues the next one.

    The worker calls task_done right before it takes the next item, so the copy
    put here at the front runs before anything another tab queued meanwhile —
    the same order Motion Collect keeps for the motion-transfer graph.
    """
    if queue is None or not callable(getattr(queue, "task_done", None)):
        return False
    if getattr(queue, "_feihou_rh_shot_hook", False):
        return True
    original = queue.task_done

    def task_done(item_id, history_result, status=None, process_item=None):
        with queue.mutex:
            item = queue.currently_running.get(item_id)
            item = copy.deepcopy(item) if item is not None else None
        result = original(item_id, history_result, status=status, process_item=process_item)
        try:
            _after_task(queue, item, status)
        except Exception:  # never break the ComfyUI worker loop
            LOGGER.exception("Easy H3 shot prompts: 排下一块失败")
        return result

    queue.task_done = task_done
    queue._feihou_rh_shot_hook = True
    return True


def _after_task(queue: Any, item: Any, status: Any) -> None:
    if not item:
        return
    run = _STANDALONE_RUNS.pop(str(item[1]), None)
    if run is None:
        return
    if not getattr(status, "completed", False):
        LOGGER.info("Easy H3 shot prompts: 分镜 %d 没有跑完，镜号不变，下次排队重跑这一块", run["block"])
        return
    progress = finish_standalone_block(run["fingerprint"], run["block"])
    server = getattr(queue, "server", None)
    if server is not None and getattr(server, "client_id", None) is not None:
        server.send_sync("feihou_rh_shot_progress", {"node": run["node"], "block": run["block"],
                                                   "shot_done": progress["done"], "shot_next": progress["next"],
                                                   "stale": bool(progress.get("stale"))},
                         server.client_id)
    # RH: the browser queues the next block on feihou_rh_shot_progress (as on RunningHub);
    # the server never puts runs into the queue itself.


SHOT_PROMPT_CLASSES = {"FeiHouEasyH3RHShotPrompts", "FeiHouEasyH3ShotPrompts"}
MOTION_SEGMENT_CLASSES = {"FeiHouEasyH3RHMotionSegment", "FeiHouEasyH3MotionSegment"}


def _motion_segment_in(prompt: Any) -> bool:
    """Does this queued graph run shots through 动作迁移分段?  Unknown graphs say yes."""
    if not isinstance(prompt, dict):
        return True
    return any(isinstance(node, dict) and node.get("class_type") in MOTION_SEGMENT_CLASSES
               for node in prompt.values())


def standalone_payload(payload: dict[str, Any], shot: "Shot") -> dict[str, Any]:
    """The block for a Sample Enhancer graph (v8 style): Setup encodes it itself.

    Joining and @continue go through the production-pack continuation
    (「视频接续（合并）」 + Video Combine V2): each series is its own pack.
    """
    from .production_continuation import CONTINUATION_KEY, continue_shot

    if shot.passthrough:
        raise ValueError(f"分镜 {shot.index} 写了 @passthrough（原片直出），只能用动作迁移工作流"
                         "（「动作迁移分段」+「动作迁移收束」）跑。")
    payload = {**payload, "motion": {**payload["motion"], "segment": False},
               "pack_key": f"shotmd_{payload['motion']['series']}",
               "transition": "continue" if shot.continues else "cut"}
    payload = continue_shot(payload)
    overlap = int((payload.get(CONTINUATION_KEY) or {}).get("overlap") or 0)
    if overlap:
        # The shot is lengthened at its start by the previous tail: the reference
        # window starts that many frames earlier so the motion stays in step.
        motion = dict(payload["motion"])
        lead = min(overlap, int(motion.get("start_frame") or 0))
        motion["start_frame"] = int(motion.get("start_frame") or 0) - lead
        motion["frames"] = int(motion.get("frames") or 0) + lead
        start, end = motion.get("range") or (shot.start, shot.end)
        motion["range"] = [max(0.0, float(start) - lead / FPS), float(end)]
        payload["motion"] = motion
    return payload


def tail_path(series: str, block: int) -> str:
    return os.path.join(series_directory(series), f"tail_{int(block):03d}.npz")


def save_tail(series: str, block: int, frames) -> str | None:
    """Keep the last frames of a block so a continued block still has an anchor."""
    import numpy as np
    import torch

    if frames is None or not hasattr(frames, "shape") or int(frames.shape[0]) == 0:
        return None
    path = tail_path(series, block)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    array = (frames.float().clamp(0, 1) * 255).round().to(torch.uint8).cpu().numpy()
    np.savez_compressed(path, frames=array)
    return path


def load_tail(series: str, block: int):
    """Load a saved block tail as IMAGE frames, or None when it is not on disk."""
    import numpy as np
    import torch

    path = tail_path(series, block)
    try:
        with np.load(path) as data:
            array = data["frames"]
    except (OSError, KeyError, ValueError):
        return None
    return torch.from_numpy(array).float().div_(255.0)


def _next_block(block: int, total: int, is_last: bool, picks: list[int] | None = None) -> int | None:
    """The block this film advances to, or None when it is finished."""
    if is_last:
        return None
    later = [int(item) for item in (picks or []) if int(item) > int(block)]
    if picks:
        return later[0] if later else None
    return min(total, int(block) + 1)


def shot_payload(shot: Shot, total: int, markdown_fingerprint: str, series: str,
                 is_last: bool | None = None, picks: list[int] | None = None) -> dict[str, Any]:
    """The production-shot dict Setup already understands, plus the motion window."""
    if is_last is None:
        is_last = shot.index >= total
    return {
        "schema": 1,
        "source": "feihou_shot_prompts",
        "id": f"S{shot.index:02d}",
        "title": f"分镜 {shot.index}/{total}",
        "index": shot.index,
        "total": total,
        "prompt": shot.prompt,
        # Media come from the Media Bridge; Setup must not clear them.
        "media": [],
        "keep_media": True,
        "pictures": list(shot.pictures),
        "pictures_explicit": bool(shot.pictures_explicit),
        "is_last": bool(is_last),
        # Setup skips all encoding and Motion Collect outputs the source frames.
        "passthrough": bool(shot.passthrough),
        "next_index": _next_block(shot.index, total, is_last, picks),
        "params": {"seconds": shot.seconds, "prompt_optimizer_enabled": False},
        "range": f"{time_text(shot.start)}-{time_text(shot.end)}",
        "motion": {
            "start_frame": shot.start_frame,
            "frames": shot.frames,
            "block": shot.index,
            "blocks": total,
            # The segment node only receives the ``motion`` sub-dict, so the stop
            # flag has to live here too.
            "is_last": bool(is_last),
            "continue": bool(shot.continues),
            "passthrough": bool(shot.passthrough),
            "fingerprint": markdown_fingerprint,
            "series": series,
            "range": [shot.start, shot.end],
            # In-block segment boundaries, frames from the block start.
            "splits": [int(round(point * FPS)) - shot.start_frame for point in shot.splits],
            "sound": shot.sound,
            # @hold: reference video 1's first frame is held this many frames in front.
            "hold_frames": shot.hold_frames,
            # @video none: Setup encodes this block without the reference videos.
            "video": bool(shot.video),
            # @first: picture card number of the block's first frame (0 = none).
            "first_picture": int(shot.first_picture),
            # @audio 分块: Setup cuts every audio card to this block's range.
            "audio_window": bool(shot.audio_window),
            # @脸部模糊: this block's source-face blur for H3 动作迁移预处理 ("" = the node's setting).
            "face_blur": shot.face_blur,
            # @分段: Motion Segment's 分段方式 自动 follows it (None = not written: 不分段).
            "segmentation": dict(shot.segmentation) if shot.segmentation else None,
            # Time-tagged dialogue lines as film-time frames: context windows keep their overlaps in the pauses.
            "speech": [[int(round(start * FPS)), int(round(end * FPS))]
                       for start, end in timed_prompt.dialogue_spans(shot.prompt)
                       if end > shot.start and start < shot.end],
        },
    }


class FeiHouEasyH3ShotPrompts:
    """Turn one markdown file into the shot the motion-transfer graph runs next."""

    CATEGORY = "FeiHou Easy H3"
    FUNCTION = "load"
    RETURN_TYPES = (SHOT_TYPE,)
    RETURN_NAMES = ("production_shot",)
    OUTPUT_NODE = True
    DESCRIPTION = (
        "动作迁移分镜提示词：把 skills 生成的分镜 md 拖到节点上、点「选择 md 文件」，或粘贴全文（每块：===== FEIHOU_SHOT nn ===== / @range / @pictures / @continue + 六段式提示词）。"
        "输出接 Setup 的「制作包分镜」口（和制作包加载器二选一），同一输出再接「动作迁移分段」的 shot_prompts。"
        "也能用在二段式采样（1st/2nd Sample Enhancer，例如 v8）工作流：图里没有「动作迁移分段」时 Setup 直接编码本块，"
        "跑完自动排下一块；@continue 和整片拼接用「视频接续（合并）」（production_shot 接本节点）+ Video Combine V2。"
        "每跑完一个分镜自动 +1，状态存在 input/feihou_h3_rh_motion，可中断续跑。"
        "改了 md 文件后点「刷新提示词」重读（浏览器记住的文件），运行时只用节点里的全文。"
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_text": ("STRING", {"multiline": True, "default": "", "tooltip":
                    "把 skills 生成的分镜 md 拖到节点上、点「选择 md 文件」，或直接粘贴全文。"
                    "RunningHub 上的运行只用这里的全文（服务器读不到你电脑上的文件）。"}),

                "start": ([START_AUTO, START_RESTART, START_MANUAL], {"default": START_AUTO, "tooltip":
                    "自动续接：从下面「镜号」那一块往后跑，每跑完一块镜号自动 +1。"
                    "从头开始：从第 1 块重跑全片，镜号跟着 +1。手动设置：只跑镜号里列出的块（例如 6,9 或 3-5），镜号保持不变。"}),
                "shot_numbers": ("STRING", {"default": "0", "tooltip":
                    "镜号：0 = 全片。左右箭头 ±1、按住左右拖动可调；单击可输入，手动设置时可填 6,9 或 3-5。"
                    "自动续接时每跑完一块自动改成下一块，整片跑完回到 0。"}),

            },
            "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"},
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")  # the current shot advances after every block

    @staticmethod
    def load(prompt_text="", md_path="", start=START_AUTO, shot_numbers="", prompt=None, unique_id=None):
        text = str(prompt_text or "")
        if not text.strip():
            raise ValueError("分镜提示词：还没有内容。把 md 拖到节点上、点「选择 md 文件」，或者把 md 全文粘贴到提示词框。")
        shots = parse_shot_prompts(text)
        markdown_fingerprint = fingerprint(text)
        total = len(shots)
        state = read_state(markdown_fingerprint)
        picks = parse_picks(shot_numbers, total) if str(start) == START_MANUAL else []

        if start == START_RESTART:
            block, series = 1, new_series(markdown_fingerprint)
        elif start == START_MANUAL:
            if not picks:
                picks = list(range(1, total + 1))  # 镜号 0 = the whole film
            resumable = (state is not None and not state.get("done")
                         and [int(item) for item in (state.get("picks") or [])] == picks)
            block = max(1, min(total, int(state.get("block") or picks[0]))) if resumable else picks[0]
            series = ((str(state.get("series") or "") if resumable else "")
                      or new_series(markdown_fingerprint))
        else:
            resumable = state is not None and not state.get("done")
            if resumable:
                # The frontend switches to 自动续接 while it queues the remaining
                # blocks, so the pick list of the running batch has to survive.
                picks = [int(item) for item in (state.get("picks") or [])]
            wanted = parse_picks(shot_numbers, total)
            if wanted:
                # The 镜号 widget doubles as "jump to this block".
                block = wanted[0]
                series = (str((state or {}).get("series") or "") if resumable else "")
            else:
                block = max(1, min(total, int(state.get("block") or 1))) if resumable else 1
            # A finished film starts over as a new series: reusing the old name
            # would overwrite the videos and manifest V2 already joined.
            series = (str(state.get("series") or "") if resumable else "") or new_series(markdown_fingerprint)
            if resumable:
                LOGGER.info("Easy H3 shot prompts: 从分镜 %d/%d 继续（series %s）", block, total, series)

        write_state(markdown_fingerprint, {"block": block, "total": total, "series": series,
                                           "done": False, "picks": picks})
        shot = shots[block - 1]
        # The film ends at its last block, a filtered run at its last pick.
        is_last = (block >= max(picks)) if picks else (block >= total)
        payload = shot_payload(shot, total, markdown_fingerprint, series, is_last, picks)
        # Without 动作迁移分段 (1st/2nd Sample Enhancer graphs such as v8) Setup
        # encodes the block itself and the browser advances 镜号 after the run.
        standalone = not _motion_segment_in(prompt)
        if standalone:
            payload = standalone_payload(payload, shot)
            _remember_standalone_run(unique_id, markdown_fingerprint, block, start)
            LOGGER.info("Easy H3 shot prompts: 没有「动作迁移分段」，按采样增强工作流跑（Setup 直接编码本块，"
                        "接续 / 拼接用「视频接续（合并）」+ Video Combine V2）")
        LOGGER.info("Easy H3 shot prompts: 分镜 %d/%d %s (%ss, %s, continue=%s%s, series %s)",
                    block, total, payload["range"], shot.seconds,
                    "原片直出，不采样" if shot.passthrough else f"pictures={list(shot.pictures) or '全部'}",
                    shot.continues, f", first=图卡 {shot.first_picture}" if shot.first_picture else "", series)
        ui = {"feihou_rh_shot": [{
            "index": block, "total": total, "series": series, "prompt": shot.prompt,
            "next": payload.get("next_index"),
            "range": payload["range"], "seconds": shot.seconds,
            "pictures": list(shot.pictures), "continue": bool(shot.continues),
            "standalone": standalone, "fingerprint": markdown_fingerprint, "is_last": bool(is_last),
        }]}
        return {"ui": ui, "result": (payload,)}
