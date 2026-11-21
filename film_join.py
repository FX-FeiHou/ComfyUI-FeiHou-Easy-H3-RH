"""完整视频拼接 · RH: join the block videos of a shot-md film into one video.

On RunningHub every queued block is its own task, usually on another machine,
so the block videos saved by earlier runs are not on this machine's disk.  The
browser records each block video as it is saved (its RunningHub file URL, or
the local file) in this node's ``block_videos`` field; the film's last block
downloads the earlier ones, adds its own frames and writes ``<name>_完整.mp4``.
Every block video is still saved on its own by the video node fed by Motion
Collect.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import uuid
from fractions import Fraction

import folder_paths
from comfy_api.latest import InputImpl, Types

from .production_continuation import SAVE_KEY

LOGGER = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 300
JOIN_AUDIO_RATE = 48000


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    return shutil.which("ffmpeg")


def parse_block_videos(text) -> dict[int, dict]:
    """{block number: {url, filename, subfolder, type}} from the browser's record (JSON)."""
    try:
        data = json.loads(str(text or "").strip() or "{}")
    except ValueError:
        return {}
    videos = data.get("videos") if isinstance(data, dict) else None
    if not isinstance(videos, dict):
        return {}
    result = {}
    for key, value in videos.items():
        if str(key).isdigit() and isinstance(value, dict):
            result[int(key)] = value
    return result


def _local_file(entry: dict) -> str | None:
    """The saved video on this machine, when it is here (a local run)."""
    name = os.path.basename(str(entry.get("filename") or ""))
    if not name:
        return None
    try:
        base = folder_paths.get_directory_by_type(str(entry.get("type") or "output"))
    except Exception:
        base = None
    if not base:
        return None
    subfolder = str(entry.get("subfolder") or "")
    path = os.path.realpath(os.path.join(base, subfolder, name))
    if not path.startswith(os.path.realpath(base)) or not os.path.isfile(path):
        return None
    return path


def _download(url: str, target: str) -> str:
    if not re.match(r"^https?://", str(url or ""), re.I):
        raise ValueError(f"不是可下载的地址：{url!r}")
    request = urllib.request.Request(url, headers={"User-Agent": "ComfyUI-FeiHou-Easy-H3-RH"})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response, open(target, "wb") as stream:
        shutil.copyfileobj(response, stream, 1 << 20)
    return target


def _probe(ffmpeg: str, path: str) -> tuple[bool, float | None]:
    """(has an audio stream, duration in seconds) from ffmpeg's header dump."""
    probe = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, check=False)
    text = probe.stderr.decode("utf-8", errors="replace")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    seconds = (int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))) if match else None
    return "Audio:" in text, seconds


def _normalize(ffmpeg: str, source: str, target: str, width: int, height: int, fps: float) -> None:
    """Re-encode one piece to the film's size, frame rate and stereo 48 kHz AAC (silence when it has none)."""
    # fps first: at the end of this chain ffmpeg dropped the last frame.
    scale = (f"fps={fps:g},scale={width}:{height}:force_original_aspect_ratio=decrease,"
             f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1")
    command = [ffmpeg, "-v", "error", "-y", "-i", source]
    audio, seconds = _probe(ffmpeg, source)
    if not audio:
        command += ["-f", "lavfi", "-i", f"anullsrc=r={JOIN_AUDIO_RATE}:cl=stereo"]
    # The piece keeps every video frame: the sound is padded with silence and cut at
    # the picture's length (-shortest would cut the picture at an AAC frame instead).
    command += ["-map", "0:v:0", "-map", "0:a:0" if audio else "1:a:0", "-vf", scale, "-af", "apad",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", str(JOIN_AUDIO_RATE), "-ac", "2"]
    command += ["-t", f"{seconds:.6f}"] if seconds else ["-shortest"]
    command += ["-movflags", "+faststart", target]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace")[-800:])


def _concat(ffmpeg: str, pieces: list[str], target: str, folder: str) -> None:
    listing = os.path.join(folder, f"concat_{uuid.uuid4().hex}.txt")
    with open(listing, "w", encoding="utf-8") as stream:
        for path in pieces:
            stream.write("file '" + os.path.abspath(path).replace("\\", "/").replace("'", "'\\''") + "'\n")
    command = [ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing,
               "-map", "0", "-c", "copy", "-movflags", "+faststart", target]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace")[-800:])


def _write_block(frames, audio, fps: float, path: str) -> None:
    frames = frames.float().clamp(0, 1)
    video = InputImpl.VideoFromComponents(Types.VideoComponents(
        images=frames, audio=audio, frame_rate=Fraction(round(float(fps) * 1000), 1000)))
    video.save_to(path, format=Types.VideoContainer.MP4, codec=Types.VideoCodec.H264)


_DATE_TOKEN = re.compile(r"%date:([^%]+)%")


def expand_prefix(text: str, now=None) -> str:
    """%date:yyyy-MM-dd% and the like, as ComfyUI's browser replaces them for its save nodes.

    The browser does not replace them for this node (seen on RunningHub), so the
    file was named after the raw text; a prefix already replaced is left as it is.
    """
    import time

    stamp = time.localtime() if now is None else now

    def replace(match):
        out = match.group(1)
        for token, value in (("yyyy", f"{stamp.tm_year:04d}"), ("yy", f"{stamp.tm_year % 100:02d}"),
                             ("MM", f"{stamp.tm_mon:02d}"), ("dd", f"{stamp.tm_mday:02d}"),
                             ("hh", f"{stamp.tm_hour:02d}"), ("mm", f"{stamp.tm_min:02d}"),
                             ("ss", f"{stamp.tm_sec:02d}")):
            out = out.replace(token, value)
        return out

    return _DATE_TOKEN.sub(replace, str(text or ""))


def _even(value: int) -> int:
    return max(2, int(value) // 2 * 2)


class FeiHouEasyH3FilmJoin:
    CATEGORY = "FeiHou Easy H3"
    FUNCTION = "join"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = (
        "完整视频拼接：接「动作迁移收束」的 images / audio / series_latent / fps。前面的分镜块不做事（每块视频照常由接在收束 images 上的视频节点保存），"
        "全片最后一块跑完时，把前面各块的视频和这一块拼成「_完整」视频。RunningHub 上每块是单独的任务、常在别的机器上，"
        "浏览器会把每块保存的视频地址记进 block_videos，这里按地址下载回来再拼，不用改。"
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "接「动作迁移收束」的 images（这一块的画面）。"}),
                "series_latent": ("LATENT", {"tooltip": "接「动作迁移收束」的 series_latent：告诉这个节点现在是第几块、一共几块。"}),
                "fps": ("FLOAT", {"forceInput": True, "tooltip": "接「动作迁移收束」的 fps。"}),
                "filename_prefix": ("STRING", {"default": "%date:yyyy-MM-dd%/%date:yyyyMMdd_hhmmss%_Minimax_H3",
                                               "tooltip": "完整视频的文件名前缀，文件名后面加「_完整」。"}),
                "block_videos": ("STRING", {"default": "", "multiline": True,
                                            "tooltip": "浏览器自动记录的每块视频（每块保存后写入，运行时只读这里），不用手动改。"
                                                       "换了分镜 md 或从第 1 块重跑时自动清空。"}),
            },
            "optional": {
                "audio": ("AUDIO", {"tooltip": "接「动作迁移收束」的 audio（这一块的声音）。"}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    @staticmethod
    def join(images, series_latent, fps, filename_prefix, block_videos, audio=None):
        series = series_latent.get(SAVE_KEY) if isinstance(series_latent, dict) else None
        series = series if isinstance(series, dict) else {}
        index, total = int(series.get("index") or 1), int(series.get("total") or 1)
        if total < 2 or index < total:
            LOGGER.info("Easy H3 完整视频拼接：分镜 %d/%d，等最后一块跑完再拼", index, total)
            return {"ui": {"feihou_rh_join": [{"waiting": True, "index": index, "total": total}]}}
        ffmpeg = _ffmpeg()
        if not ffmpeg:
            raise RuntimeError("完整视频拼接需要 ffmpeg（imageio-ffmpeg 或系统 ffmpeg），这台机器上没有找到。")
        fps = float(fps or 24.0)
        height, width = _even(images.shape[1]), _even(images.shape[2])
        recorded = parse_block_videos(block_videos)
        folder = tempfile.mkdtemp(prefix="feihou_h3_join_", dir=folder_paths.get_temp_directory())
        missing, pieces = [], []
        try:
            for block in range(1, total):
                entry = recorded.get(block)
                if not entry:
                    missing.append(block)
                    continue
                source = _local_file(entry)
                if source is None:
                    url = str(entry.get("url") or "")
                    try:
                        source = _download(url, os.path.join(folder, f"block_{block:03d}_src.mp4"))
                    except Exception as exc:
                        LOGGER.warning("Easy H3 完整视频拼接：分镜 %d 的视频下载失败（%s）：%s", block, url, exc)
                        missing.append(block)
                        continue
                piece = os.path.join(folder, f"block_{block:03d}.mp4")
                _normalize(ffmpeg, source, piece, width, height, fps)
                pieces.append(piece)
            current = os.path.join(folder, f"block_{total:03d}_src.mp4")
            _write_block(images[:, :height, :width], audio, fps, current)
            piece = os.path.join(folder, f"block_{total:03d}.mp4")
            _normalize(ffmpeg, current, piece, width, height, fps)
            pieces.append(piece)
            if missing:
                LOGGER.warning("Easy H3 完整视频拼接：缺分镜 %s 的视频（没有记录或下载失败），用现有的 %d 块拼",
                               "、".join(str(block) for block in missing), len(pieces))
            out_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
                expand_prefix(filename_prefix) or "FeiHou_H3", folder_paths.get_output_directory(), width, height)
            name = f"{filename}_{counter:05}_完整.mp4"
            target = os.path.join(out_folder, name)
            _concat(ffmpeg, pieces, target, folder)
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        LOGGER.info("Easy H3 完整视频拼接：%d 块拼成 %s", len(pieces), os.path.join(subfolder, name))
        video = {"filename": name, "subfolder": subfolder, "type": "output", "format": "video/h264-mp4",
                 "frame_rate": fps}
        return {"ui": {"gifs": [video],
                       "feihou_rh_join": [{"joined": len(pieces), "total": total, "missing": missing}]}}
