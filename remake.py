# SPDX-License-Identifier: Apache-2.0
"""Remake 替换模式: the conditioning the Viggle Remake swap LoRA was trained on.

Written after Viggle's ComfyUI nodes (Apache-2.0, huggingface.co/Viggle/Viggle-Remake);
nothing here imports them.  Compared with Easy H3's own reference mode:

* the source video is presented text-only: a ``<Video 1>:`` label with one
  ``<N seconds>`` stamp per 2 fps block, then ``<Picture N>:`` per image, then
  the prompt, each tokenized on its own (no vision tokens);
* the source video block carries no audio; its soundtrack (or silence) is the
  clean target audio, held with noise_mask 0 for the whole denoise;
* the source is encoded on the output canvas (pixel-aligned with the result),
  pictures at the output's short edge;
* sampling uses the swap schedule (6 steps), keyframes are dropped once
  sigma falls below 0.9;
* a continued segment opens with the previous frames held clean (prefix)
  instead of a keyframe guide.
"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict

import torch

import comfy.audio
import comfy.nested_tensor
import comfy.patcher_extension
import comfy.utils

FPS = 24
# Viggle's swap schedule (ManualSigmas of their remake_swap workflow).
SWAP_SIGMAS = (1.0, 0.990476, 0.965243, 0.923077, 0.8, 0.631579, 0.0)
KEYFRAME_UNTIL = 0.9
# The H3 video VAE encodes 17-frame groups into 5 latent frames.
PREFIX_GROUP = 17
WRAPPER_KEY = "feihou_easy_h3_remake_keyframe_until"


def swap_sigmas() -> torch.Tensor:
    return torch.tensor(SWAP_SIGMAS, dtype=torch.float32)


def lanczos(image: torch.Tensor, width: int, height: int) -> torch.Tensor:
    return comfy.utils.common_upscale(image[..., :3].movedim(-1, 1), width, height, "lanczos", "disabled").movedim(1, -1)


def cover(frames: torch.Tensor, width: int, height: int, chunk: int = 16) -> torch.Tensor:
    """Scale to cover ``width`` x ``height`` and centre-crop (frames in chunks)."""
    h, w = int(frames.shape[1]), int(frames.shape[2])
    if (h, w) == (height, width):
        return frames[..., :3]
    scale = max(width / w, height / h)
    sw, sh = max(width, round(w * scale)), max(height, round(h * scale))
    left, top = (sw - width) // 2, (sh - height) // 2
    parts = [lanczos(frames[i:i + chunk], sw, sh)[:, top:top + height, left:left + width]
             for i in range(0, int(frames.shape[0]), chunk)]
    return torch.cat(parts)


def picture_size(height: int, width: int, short_edge: int) -> tuple[int, int]:
    """A picture at the output's short edge, both sides rounded to 32 (no area cap)."""
    th = max(32, round(height * short_edge / min(height, width) / 32) * 32)
    tw = max(32, round(width * short_edge / min(height, width) / 32) * 32)
    return tw, th


def stamps(frames: int) -> list[float]:
    """The conditioner's 2 fps block labels of a clip: every 12th frame, merged in pairs, mean time of each pair."""
    idx, cursor = [], 0.0
    while round(cursor) < frames:
        if not idx or round(cursor) > idx[-1]:
            idx.append(round(cursor))
        cursor += FPS / 2
    t = [i / 2 for i in range(len(idx))]
    t += t[-1:] * (len(t) % 2)
    return [(t[i] + t[i + 1]) / 2 for i in range(0, len(t), 2)]


def label_segments(frames: int, pictures: int, prompt: str) -> tuple[str, ...]:
    return ("<Video 1>: ", *("<%.1f seconds>" % s for s in stamps(frames)),
            *("<Picture %d>: " % (i + 1) for i in range(pictures)), str(prompt))


def tokenize(clip, segments) -> dict:
    """Each segment tokenized on its own, concatenated (one batch)."""
    merged: dict = {}
    for segment in segments:
        for key, batches in clip.tokenize(segment).items():
            merged.setdefault(key, [[]])[0].extend(batches[0])
    return merged


def held_audio_latent(audio_vae, audio, latent: dict, frames: int) -> dict:
    """``latent`` with the soundtrack (silence when None) as clean target audio, noise_mask 0."""
    video, empty_audio = latent["samples"].unbind()
    audio_t = int(empty_audio.shape[-1])
    rate = int(getattr(audio_vae, "audio_sample_rate", 32000))
    n = round((frames + 1) / FPS * rate)
    wav = torch.zeros(2, n)
    if isinstance(audio, dict) and isinstance(audio.get("waveform"), torch.Tensor):
        wav, sr = audio["waveform"][0].float().cpu(), int(audio["sample_rate"])
        wav = wav.repeat(2, 1) if wav.shape[0] == 1 else wav[:2]
        wav = wav[:, :round(frames / FPS * sr)]
        if sr != rate:
            wav = comfy.audio.resample(wav, sr, rate)
    wav = torch.nn.functional.pad(wav, (0, max(0, n - wav.shape[1])))[:, :n]
    # Whole 800-sample latent frames: VAE.encode would centre-crop instead and shift the track.
    wav = torch.nn.functional.pad(wav, (0, -n % 800))
    held = audio_vae.encode(wav[None].movedim(1, -1))[..., :audio_t]
    if held.shape[-1] < audio_t:
        held = torch.nn.functional.pad(held, (0, audio_t - held.shape[-1]))
    held = held.to(empty_audio)
    output = dict(latent)
    output["samples"] = comfy.nested_tensor.NestedTensor((video, held))
    output["noise_mask"] = comfy.nested_tensor.NestedTensor((torch.ones_like(video), torch.zeros_like(held)))
    return output


def prefix_frames(skip: int) -> int:
    """Frames of a continued segment's head that can be held clean (whole 17-frame groups)."""
    return int(skip) // PREFIX_GROUP * PREFIX_GROUP


def apply_prefix(video_vae, latent: dict, prefix: torch.Tensor) -> dict:
    """The previous frames open this render, held clean (noise_mask 0) like the soundtrack."""
    k = int(prefix.shape[0])
    video, audio = latent["samples"].unbind()
    n = k // PREFIX_GROUP * 5
    if k % PREFIX_GROUP or not 0 < n < video.shape[2]:
        raise ValueError(f"Remake prefix needs a multiple of 17 frames shorter than the render, got {k}")
    mask = latent.get("noise_mask")
    if mask is not None:
        vmask, amask = mask.unbind()
    else:
        vmask, amask = torch.ones_like(video), torch.ones_like(audio)
    # The VAE encodes 17-frame groups and drops the last 3 latents: pad to 17m + 5, keep the first 5m.
    clean = video_vae.encode(torch.cat([prefix[..., :3], prefix[-1:, ..., :3].repeat(5, 1, 1, 1)]))[:, :, :n]
    video, vmask = video.clone(), vmask.clone()
    video[:, :, :n] = clean.to(video)
    vmask[:, :, :n] = 0
    output = dict(latent)
    output["samples"] = comfy.nested_tensor.NestedTensor((video, audio))
    output["noise_mask"] = comfy.nested_tensor.NestedTensor((vmask, amask))
    return output


# 原片脸部模糊 (H3 动作迁移预处理): the source face is blurred before <Video 1> is
# encoded, so the swap takes the look from the pictures while head, eye and
# mouth movement still show.  Strength = face width / Gaussian sigma (smaller =
# stronger).  自动 picks a strength per frame from how big the face is: a far,
# small face is barely blurred, a close-up gets the strongest level.
FACE_BLUR_OFF = "关"
FACE_BLUR_AUTO = "自动"
LEVEL_DIVISORS = {1: 40.0, 2: 26.0, 3: 18.0, 4: 13.0, 5: 9.0}
FACE_BLUR_CHOICES = [FACE_BLUR_OFF, FACE_BLUR_AUTO, "1档", "2档", "3档", "4档", "5档"]
# 自动: face box height / frame height at which each level is reached (linear in between).
AUTO_RATIOS = ((0.04, 0.0), (0.07, 1.0), (0.10, 2.0), (0.14, 3.0), (0.18, 4.0), (0.22, 5.0))
FACE_DETECTOR = "face_yolov8m.pt"
# Frames a missed detection is bridged across (a face that leaves for longer is not blurred).
MAX_GAP = 12
_FACE_BOXES: OrderedDict = OrderedDict()
_FACE_BOX_LIMIT = 20000


def parse_face_blur(value):
    """None (关), an int level 1-5, or "auto", from a node choice or an md value (``3``, ``3档``, ``自动``, ``auto``)."""
    text = str(value if value is not None else "").strip().lower().replace("档", "").replace("级", "")
    if text in {"", "0", "关", "off", "none", "no", "false", "不模糊", "无"}:
        return None
    if text in {"自动", "auto"}:
        return "auto"
    if text.isdigit() and 1 <= int(text) <= 5:
        return int(text)
    raise ValueError(f"脸部模糊只能是 关 / 自动 / 1–5 档，得到「{value}」")


def level_divisor(level: float) -> float:
    """Divisor of a (fractional) level; 0 = no blur.  Interpolated in 1/divisor (blur strength)."""
    if level < 0.5:
        return 0.0
    low = max(1, min(5, int(level)))
    high = min(5, low + 1)
    frac = min(1.0, max(0.0, level - low))
    strength = (1 - frac) / LEVEL_DIVISORS[low] + frac / LEVEL_DIVISORS[high]
    return 1.0 / strength


def auto_level(box, frame_height: int) -> float:
    """自动: the level for a face this big in the frame."""
    ratio = (box[3] - box[1]) / max(1, frame_height)
    if ratio <= AUTO_RATIOS[0][0]:
        return 0.0
    for (r0, l0), (r1, l1) in zip(AUTO_RATIOS, AUTO_RATIOS[1:]):
        if ratio <= r1:
            return l0 + (l1 - l0) * (ratio - r0) / (r1 - r0)
    return AUTO_RATIOS[-1][1]


def _frame_key(frame: torch.Tensor, detector: str) -> bytes:
    """Content key of one frame, independent of its size: the same source frame in
    overlapping windows, the preview and the enlarged 2nd pass is detected once."""
    thumb = torch.nn.functional.interpolate(frame[..., :3].movedim(-1, 0)[None].float(), size=(32, 32), mode="area")
    coarse = (thumb.clamp(0, 1) * 31).round().to(torch.uint8)
    return hashlib.sha1(coarse.numpy().tobytes() + detector.encode("utf-8")).digest()


def detector_choices() -> list:
    """Face detectors installed under the ultralytics bbox folders, face_yolov8m first."""
    try:
        from .face_refine import _detectors
        return _detectors()
    except Exception:
        return [FACE_DETECTOR]


def _detector(name: str = FACE_DETECTOR):
    try:
        from . import face_refine_tracking
        return face_refine_tracking._load_detector(name)
    except ImportError as exc:
        raise RuntimeError("H3 动作迁移预处理的脸部模糊需要 ultralytics（人脸精修用的同一个库），当前环境没有安装。") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"H3 动作迁移预处理的脸部模糊找不到人脸检测模型 {name}，"
                           "请放到 models/ultralytics/bbox/。") from exc


def face_boxes(frames: torch.Tensor, detector: str = FACE_DETECTOR, confidence: float = 0.3, batch: int = 16,
               progress=None) -> list:
    """Largest face box (x1, y1, x2, y2) of every frame, None where none is found.

    Boxes are cached as fractions of the frame, so a cached frame of another size
    maps back correctly.  ``progress(done)`` is called after each detected batch.
    """
    height, width = int(frames.shape[1]), int(frames.shape[2])
    keys = [_frame_key(frame, detector) for frame in frames]
    todo, queued = [], set()
    for i, key in enumerate(keys):
        if key not in _FACE_BOXES and key not in queued:     # identical frames are detected once
            queued.add(key)
            todo.append(i)
    if todo:
        model = _detector(detector)
        for begin in range(0, len(todo), batch):
            chunk = todo[begin:begin + batch]
            images = [(frames[i, ..., :3].clamp(0, 1) * 255).round().to(torch.uint8).cpu().numpy()[..., ::-1].copy()
                      for i in chunk]
            for i, result in zip(chunk, model.predict(images, conf=confidence, verbose=False)):
                best = None
                for x1, y1, x2, y2 in result.boxes.xyxy.cpu().tolist():
                    if best is None or (x2 - x1) * (y2 - y1) > (best[2] - best[0]) * (best[3] - best[1]):
                        best = (x1, y1, x2, y2)
                _FACE_BOXES[keys[i]] = None if best is None else (
                    best[0] / width, best[1] / height, best[2] / width, best[3] / height)
                if len(_FACE_BOXES) > _FACE_BOX_LIMIT:
                    _FACE_BOXES.popitem(last=False)
            if progress is not None:
                progress(min(len(todo), begin + batch))
    out = []
    for key in keys:
        box = _FACE_BOXES.get(key)
        out.append(None if box is None else (box[0] * width, box[1] * height, box[2] * width, box[3] * height))
    return out


def _smooth_boxes(boxes: list) -> list:
    """Bridge short misses from the nearest detected frame, then a 5-frame median against jitter."""
    found = [i for i, box in enumerate(boxes) if box is not None]
    if not found:
        return list(boxes)
    filled = []
    for i, box in enumerate(boxes):
        nearest = min(found, key=lambda j: abs(j - i))
        filled.append(box if box is not None else (boxes[nearest] if abs(nearest - i) <= MAX_GAP else None))
    out = []
    for i, box in enumerate(filled):
        if box is None:
            out.append(None)
            continue
        near = torch.tensor([b for b in filled[max(0, i - 2):i + 3] if b is not None], dtype=torch.float64)
        out.append(tuple(near.median(dim=0).values.tolist()))
    return out


def _gaussian(image: torch.Tensor, sigma: float) -> torch.Tensor:
    """Separable Gaussian blur of [C, H, W]."""
    radius = max(1, int(sigma * 3))
    x = torch.arange(-radius, radius + 1, dtype=image.dtype)
    kernel = torch.exp(-(x * x) / (2 * sigma * sigma))
    kernel = kernel / kernel.sum()
    channels = image.shape[0]
    padded = torch.nn.functional.pad(image[None], (radius, radius, radius, radius), mode="replicate")
    out = torch.nn.functional.conv2d(padded, kernel.view(1, 1, 1, -1).repeat(channels, 1, 1, 1), groups=channels)
    out = torch.nn.functional.conv2d(out, kernel.view(1, 1, -1, 1).repeat(channels, 1, 1, 1), groups=channels)
    return out[0]


def blur_face(frame: torch.Tensor, box, divisor: float) -> torch.Tensor:
    """One frame [H, W, C] with a feathered ellipse over the face box Gaussian-blurred."""
    if divisor <= 0:
        return frame
    x1, y1, x2, y2 = box
    height, width = int(frame.shape[0]), int(frame.shape[1])
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    ax, ay = bw * 0.62, bh * 0.68          # brows to chin, cheek to cheek
    sigma = max(1.5, bw / divisor)
    # Soft edge: a solid ellipse Gaussian-blurred with sigma = 6% of the face width
    # (the edge spans about a quarter of the face width).
    feather = max(1.0, bw * 0.06)
    margin = 3 * sigma + 3 * feather
    left, right = max(0, int(cx - ax - margin)), min(width, int(cx + ax + margin) + 1)
    top, bottom = max(0, int(cy - ay - margin)), min(height, int(cy + ay + margin) + 1)
    if right - left < 2 or bottom - top < 2:
        return frame
    region = frame[top:bottom, left:right, :3].float()
    soft = _gaussian(region.movedim(-1, 0), sigma).movedim(0, -1)
    ys = torch.arange(top, bottom, dtype=torch.float32)[:, None]
    xs = torch.arange(left, right, dtype=torch.float32)[None, :]
    distance = torch.sqrt(((xs - cx) / ax) ** 2 + ((ys - cy) / ay) ** 2)
    # Pixels inside the ellipse edge, divided by the edge sigma: the profile of a blurred hard ellipse.
    inside = (1 - distance) * torch.sqrt(torch.tensor(ax * ay, dtype=torch.float32))
    mask = (0.5 * (1 + torch.erf(inside / (feather * 2 ** 0.5))))[..., None]
    out = frame.clone()
    out[top:bottom, left:right, :3] = (region * (1 - mask) + soft * mask).to(frame.dtype)
    return out


def blur_plan(boxes: list, setting, frame_height: int) -> list:
    """Divisor of every frame (0 = leave it): a fixed level, or 自动 from each face's size averaged over 9 frames."""
    if setting in (None, 0):
        return [0.0] * len(boxes)
    if setting == "auto":
        raw = [auto_level(box, frame_height) if box is not None else 0.0 for box in boxes]
        levels = [sum(raw[max(0, i - 4):i + 5]) / len(raw[max(0, i - 4):i + 5]) for i in range(len(raw))]
    else:
        levels = [float(setting)] * len(boxes)
    return [level_divisor(level) if box is not None else 0.0 for level, box in zip(levels, boxes)]


def describe_plan(boxes: list, setting, frame_height: int) -> str:
    if setting == "auto":
        raw = [auto_level(box, frame_height) for box in boxes if box is not None]
        return f"自动，按脸的大小 {min(raw):.1f}–{max(raw):.1f} 档" if raw else "自动"
    return f"{int(setting)} 档"


def blur_faces(frames: torch.Tensor, setting, detector: str = FACE_DETECTOR) -> torch.Tensor:
    """Every frame's face blurred (frames [N, H, W, C], 0-1).

    ``setting``: None / 0 = off, an int level 1-5, or "auto" (level from each
    frame's face size, averaged over 9 frames so it does not flicker).
    """
    if setting in (None, 0) or int(frames.shape[0]) == 0:
        return frames
    boxes = _smooth_boxes(face_boxes(frames, detector))
    if all(box is None for box in boxes):
        logging.warning("Easy H3 动作迁移预处理：这一窗 %d 帧都没检测到人脸，原片不做模糊", len(boxes))
        return frames
    divisors = blur_plan(boxes, setting, int(frames.shape[1]))
    logging.info("Easy H3 动作迁移预处理：脸部模糊 %s，%d 帧", describe_plan(boxes, setting, int(frames.shape[1])), len(boxes))
    return torch.stack([blur_face(frame, box, divisor) if box is not None else frame
                        for frame, box, divisor in zip(frames, boxes, divisors)])


def write_preview(path: str, frames_of, count: int, boxes: list, divisors: list, fps: float = FPS,
                  chunk: int = 32, progress=None) -> None:
    """Encode the blurred frames to an H.264 mp4, ``chunk`` frames at a time (``frames_of(start, stop)``)."""
    import av

    with av.open(path, mode="w") as container:
        stream = None
        for start in range(0, count, chunk):
            frames = frames_of(start, min(count, start + chunk))
            if stream is None:
                stream = container.add_stream("libx264", rate=int(round(fps)))
                stream.width, stream.height = int(frames.shape[2]), int(frames.shape[1])
                stream.pix_fmt = "yuv420p"
                stream.options = {"crf": "20", "preset": "veryfast"}
            for offset, frame in enumerate(frames):
                index = start + offset
                if boxes[index] is not None and divisors[index] > 0:
                    frame = blur_face(frame, boxes[index], divisors[index])
                pixels = (frame[..., :3].clamp(0, 1) * 255).round().to(torch.uint8).cpu().numpy()
                for packet in stream.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")):
                    container.mux(packet)
            if progress is not None:
                progress(min(count, start + chunk))
        if stream is not None:
            for packet in stream.encode():
                container.mux(packet)


def keyframe_until(model, until: float = KEYFRAME_UNTIL):
    """Drop the keyframes from every forward whose sigma is below ``until``; the references remain."""
    def release(executor, x, timestep, context, transformer_options, minimax_payload=None, **kwargs):
        payload = minimax_payload or {}
        if payload.get("keyframes") and float(timestep.flatten()[0]) / 1000 < until:
            refs = payload.get("refs") or []
            minimax_payload = dict(payload, keyframes=None, layout=None,
                                   cond_video_latents=[r["latent"] for r in refs if "latent" in r],
                                   cond_audio_latents=[r["audio_latent"] for r in refs
                                                       if r.get("audio_latent") is not None])
        return executor(x, timestep, context, transformer_options, minimax_payload=minimax_payload, **kwargs)

    if WRAPPER_KEY in (getattr(model, "wrappers", {}) or {}).get(comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL, {}):
        return model
    patched = model.clone()
    patched.add_wrapper_with_key(comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL, WRAPPER_KEY, release)
    return patched
