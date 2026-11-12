# Changelog

## v1.4.18

- Context windows now work for talk blocks (`@video none`) whose dialogue lines are time-tagged, e.g. `[00:09.00-00:12.60] <Subject 1> (S1) 看着镜头说：<d>…</d>`. Each window speaks only the lines it holds at least half of, so a sentence is never started by two windows. The windows are placed so their overlaps fall in the pauses between lines: a window may be shorter than the set length (down to about 5 s), and speech in the middle of an overlap counts most. The log reports any speech frames left in an overlap. When a window's first line starts more than 0.5 s into the window, or its last line ends more than 0.5 s before the end, the prompt gets a short note to keep the mouth closed there (Chinese or English, following the line). A talk block without time tags keeps the sequential frame-window segments. Untagged lines still go to every window, so camera moves meant to happen once should be tagged too.
- H3动作迁移预处理 / Motion Segment: a talk block (`@video none`) now skips Remake 替换 and the face blur, because it has no source video to edit (it used to stop with "Remake 替换模式需要参考视频 1"). The preprocess node no longer runs face detection or a preview for such a block. The log of a context-window block lists each window's length when they differ, and counts only the spoken frames left in overlaps (lip padding excluded).
- Motion Segment: 分段方式 has a new first choice **自动** (now the default): the shot md decides with `@分段` — in the md header for every block, or in a block to override it, written with named fields, e.g. `@分段 上下文窗口 窗口=192 重叠=34 每段=30秒` (每段 can be 整块), `@分段 帧窗口 段长=124 重叠=22` or `@分段 不分段` (English names window / length / overlap / segment also work; bare numbers in that order are still read); values left out use the node's recommended ones (上下文窗口 345 / 68 / 30 秒, 帧窗口 124 / 22). Without `@分段` (or without a shot md) 自动 runs 不分段. With 自动 and 不分段 the window fields are greyed out and not used (不分段 joins `@split` segments and `@continue` blocks on 22 frames).
- Remake 替换 mode for the Viggle Remake swap LoRA, switched on in the H3动作迁移预处理 node below (`viggle_remake_swap_comfyui`, add it to the LoRA list with bypass on). Reference video 1 is the source to edit and the pictures the new look, presented the way the LoRA was trained: text-only labels (`<Video 1>:` with its 2 fps time stamps, `<Picture N>:`, then the prompt, no vision tokens), the source on the output canvas without its audio, pictures at the output's short edge, and the soundtrack held clean as the target audio (silence with 不送入模型). Sampling uses the 6-step swap schedule (steps is not used; two-pass runs its first `first_steps` steps in the 1st pass and the rest in the 2nd, second_steps is not used), keyframes are dropped below sigma 0.9 in both passes, and a continued segment opens with the previous segment's frames held clean (whole 17-frame groups of the overlap) instead of a keyframe guide. Works with shot blocks, frame windows and context windows. Written after Viggle's Apache-2.0 nodes; the Viggle node pack is not needed.
- New node **H3动作迁移预处理** (`FeiHouEasyH3RHMotionPreprocess`, H3动作迁移预处理 · RH), between Setup and Motion Segment (h3_context in and out); bypass it when not needed. Its `remake` switch is the only place Remake 替换 is turned on (Motion Segment has no switch of its own). 原片脸部模糊 has its own on/off switch (off greys out the level and detector): before reference video 1 is encoded, the face in each source frame is found with a detector from `models/ultralytics/bbox` (default `face_yolov8m.pt`) and a feathered ellipse from brows to chin is Gaussian-blurred, so in half-body shots and close-ups the look comes from the pictures instead of the original face; head position, turns, blinks and the mouth's opening still show. Levels 1–5 are fixed strengths, the edge is feathered; 自动 picks the level per frame from the face's size in the frame (far small faces about 0, half-body about 2–3, face close-ups 5), averaged over neighbouring frames. Shot md blocks can set `@脸部模糊 关/自动/1–5`, which wins over the node; with the switch off nothing is blurred. Detections are cached per frame, so overlapping context windows detect once. The film's soundtrack, color matching and 原片直出 use the untouched source. When blurring is on, the node runs face detection over the whole current block with a progress bar on the node and shows the blurred block as a preview video on the node (canvas size, with a one-line summary of frames, faces found and levels used); Motion Segment then reuses those detections, also at the 2nd pass's larger size. An optional 分镜提示词 input makes the preview follow the block's `@脸部模糊`. Needs ultralytics (the library Face Refine uses).
- Shot Prompts in a Sample Enhancer graph (two-pass v8 style, 1st/2nd Sample Enhancer · RH, no Motion Segment): Setup now encodes each md block itself instead of leaving a motion placeholder, and joining and `@continue` go through 接续合并 · RH + Video Combine V2. When a run finishes the server advances 镜号 and the browser queues the next block (on RH the server never queues runs itself). A Sample Enhancer fed by a placeholder context (Setup behind Motion Segment) now stops with a clear message.
- Shot md header `@audio 分块`: every audio card follows each block's `@range`, so a talk block sends only its own seconds of the recording as `<Audio N>`.
- Shot Prompts: an md file can also be dropped onto the prompt box, not only the title bar and menus. Fixes the shot preview after a run (it read the standard edition's ui key).
- 接续合并 · RH saves the tail of every segment, also the first one and hard cuts, so a later segment can continue any of them; 硬切 only skips the previous segment's guide.
- Setup no longer hangs on large reference videos. A gallery video without its own 媒体设置 is read at 720P when its source is larger (smaller ones as they are; 「原始」 in 媒体设置 still reads the full size), as in the standard edition; a plain generation decodes only the frames it encodes; reference frames are cut before they are resized. Decoded frames are kept as 8 bits and turned into floats only for the window being used, with the same values. A 58 s 1080p HEVC video peaked at about 43 GB of RAM (it was decoded at full size as floats) and now takes about 4.5 GB.
- Motion Segment: context-window sampling is switched back on. `segmentation` (分段方式) is now 不分段 / 帧窗口 / 上下文窗口 and replaces the `frame_window` switch; `segment_frames` / `overlap_frames` are shared by the modes and replace `context_window_frames` / `context_overlap_frames`. Each mode shows its own options (帧窗口: 39–497 frames, overlap 22 / 39 / 5; 上下文窗口: 124–362 frames, overlap 34 / 68 / 102), starts from its recommended values (124 / 22, 345 / 68) and remembers what you last set in it (`properties.feihou_segment_modes`), so switching back restores those values. 不分段 greys out `segment_frames`. A context-window block marked `@continue` anchors on 22 tail frames. Saved workflows are migrated: `frame_window` off becomes 不分段, the old context fields become the 上下文窗口 values.
- Shot md: a prompt line that starts with a time range in film time (`[00:03.50-00:08.00]` or `[3.5-8]`, the `@range` clock) is an action for that time only. Every sampled window — context window, frame-window segment, whole block, and the 2nd pass that re-encodes it — keeps only the tagged lines that overlap it by at least 0.5 s (or lie inside it), without the tag; untagged lines go to every window. A whole-prompt encode just drops the tags. Fixes context-window blocks repeating the whole timeline in every window (actions early and repeated, ghosting where windows overlap).
- Shot md: the 45 s limit per block is gone; a block can be as long as the reference video (e.g. a 91 s one-take sampled with context windows). `@split` segments stay at most 15 s and 原片直出 blocks at most 20 s.
- Context windows: every window's reference media is encoded first and every window's prompt after it, so the video VAE and the text encoder are loaded once per pass instead of once per window (a 91 s block with 15 windows swapped the 25 GB text encoder in 15 times before sampling). The reference picture is VAE-encoded once per pass. Encoded prompts are cached by content (prompt plus every picture and video frame the text encoder sees), so the same window in a rerun skips the text encoder.
- Motion Segment: new `context_segment` (上下文每段上限: 整块一次 / 20 / 30 / 45 / 60 秒, default 30 秒), used with 上下文窗口 only (greyed out otherwise). A longer block is sampled in segments of at most that length, one per run, each still with context windows; a segment starts on the previous one's last `overlap_frames` (the window overlap), anchored to its decoded frames, and that overlap cross-fades from the old segment into the new one. Results show up segment by segment and an interrupted run keeps its finished segments; total compute stays about the same.
- Motion Collect: with save_segments on, each saved segment also shows in the video node fed by Collect's images output (e.g. Video Combine V2 成片), which otherwise only runs on the block's last segment.
- Motion Collect: `filename_prefix` is removed. Saved segments go to the same folder as the joined video: the `filename_prefix` of the node fed by Collect's images output (e.g. Video Combine V2), plus `_b001_seg01` (`FeiHou_H3_motion/segment` when nothing is connected). Saved workflows keep their `color_match_strength`.

## v1.4.17

- Adds motion transfer / person swap from a shot md: **FeiHou Easy H3 Shot Prompts** (drop or pick a md, `start` 自动续接 / 从头开始 / 手动设置, 镜号 widget, md path remembered), **Motion Segment** and **Motion Collect**. One queue runs every block, saves each block and joins the film; interrupted runs resume. Run state lives in `input/feihou_h3_motion` (with an in-memory fallback); a finished film drops its tails and state, and files older than 48 h are pruned (`segment_*.mp4` are never deleted).
- Shot md directives: `@range`, `@pictures`, `@continue`, `@split` (in-block segments of at most 15 s), `@passthrough` / `@原片` (source frames, no sampling), `@sound 原声/生成`, `@video none`, header `@hold` (hold the reference video's first frame, silent) and `@first N`.
- Motion Segment: one or two passes is detected from the graph (its `h3_context` output feeding a 2nd Sample Enhancer means two-pass, with `first_steps`); `frame_window` switch (off = the whole video in one run); `segment_frames` shown with seconds; `reference_soundtrack` 送入模型 / 不送入模型; seed removed (noise comes from the workflow). Context-window sampling is in the code but switched off for now.
- Motion Collect outputs the joined film audio at 48 kHz stereo and can colour-match to the source per shot.
- Media node: per-type external sockets (`image_N`, `video_N` + `video_N_audio`, `audio_N`) that grow as you connect and renumber on disconnect; a connected input overrides the card of the same number. Video cards get 媒体设置 (frame window, frame rate); image previews are top-aligned; the node no longer grows on tab switches.
- Prompt templates: the motion template is split into 小肥猴H3人物替换 (background stays the video's and is described explicitly) and 小肥猴H3动作迁移 (background from the scene picture, the user's text or the person picture, described in detail; the video's framing and camera move are copied), each in English and Chinese.
- Windows: serves files without aiohttp sendfile, which stalls on some machines (Media cards stuck at 上传中, previews and scripts never arriving).
- RH LoRA stack: on RunningHub, clicking a selected LoRA reopens the RH LoRA resource picker and clicking the strength opens an in-place number field (the canvas bridge only delivers pointerdown reliably; `prompt()` is blocked in the embedded page).
- RH frontend metadata: every extension declares its `rh` node list; the sample-enhancer extension uses an RH-only name and class.

- Adds the shot-md directive `@first N` (`@首帧 N`): picture card N becomes the block's first frame (a keyframe at frame 0, kept in the output) when the block has no previous tail, e.g. a dance block run on its own. The card is only a keyframe, not a reference picture, so it need not be in `@pictures`. A continued block with a tail keeps the tail; both passes and context windows (first window) get the anchor.
- Adds Motion Segment `segmentation` (分段方式) = 上下文窗口 with `context_window_frames` / `context_overlap_frames`: a long shot block with reference video is denoised in one sampler run; at every step overlapping 17-frame-aligned windows are predicted with their own reference-video window (pictures and prompt in every window) and blended over the overlaps, so no window continues from decoded frames. Works for single sampling and for both passes of the two-pass chain (2nd Sample Enhancer rebuilds the same windows at its canvas). Talk blocks without reference video keep 接续; the default stays 接续.
- Motion Collect decodes such a block in clip-aligned pieces (identical frames) and keeps 8-bit frames meanwhile.

## v1.4.16

- Expands automatic duration alignment in RH Main/Setup to Video 1-3 and Audio 1-3, using each selected source's trimmed duration.
- Changes the Output node's audio output to emit the selected alignment source's audio: the video soundtrack when aligning to a video, or the trimmed audio when aligning to an audio reference. Off keeps the previous Audio 1 behaviour.
- Keeps legacy `audio`/`video`, Boolean and localized alignment values working in saved workflows. RunningHub API, authentication, billing and media transport are unchanged.

## v1.4.15

- Adds the saved RefMod filmmaking prompt rule, unchanged, as the read-only built-in `refmod` template (`RefMod`) for RH Main and Setup. Existing custom rules are preserved.
- Restores prompt-rule names after R / Refresh Node Definitions without changing RunningHub API, authentication, billing, or media transport.

## v1.4.14

- Adds optional `H3_REF_MODS` inputs to RH Main and Setup. Connect the upstream Load H3 RefMods node and use reference mode; image/video/audio MODs retain their native reference latents and strength processing.
- Adds MOD references to the prompt editor's `@` menu, preserves reference bindings across workflow saves, and appends an Output `reference_map` string without moving existing sockets. MODs lead numbering within each media type; gallery media follow and keep their existing 9-image/3-video/3-audio limits.
- Preserves MOD presentation and latent blocks during trigger-word and second-pass canvas rebuilds. Prompt optimization receives the MOD reference map through the existing RH platform or custom API path; RH billing/authentication, selectors, uploads and reference-image encoding cache are retained.
- Scope: MOD integration only. No Standard-edition edits, continuation-save changes, local LLM backend, LoRA mode restoration or attention-patch changes.
- Validation: 23 CPU integration checks including real upstream MOD/bundle round trips, isolated metadata HTTP route, RH JSON media transport and mocked platform/custom APIs; JavaScript reference/serialization checks. Live RunningHub GPU generation remains untested.

## v1.4.13

- Fails fast when the RH loader receives a MiniMax Music3 audio encoder. Music3 produces 32768-wide autoregressive audio states and cannot provide H3's raw 5120-wide Qwen3-VL conditioning; the error now appears during loading instead of after a long Setup/Enhancer encode.
- Keeps renamed H3 text-encoder files supported and directs users to the compatible Qwen3-VL-32B encoder.
- Fixes RH Face Refine's diagnostic path when the context adapter has no `clip_name`; face refinement can proceed without the logging-only `SimpleNamespace` attribute error.
- Validation: focused CPU/mock regressions, Python/JSON syntax, and synchronized source/install hashes. Live RunningHub GPU generation remains untested.

## v1.4.12

- Fixes RH Remix second-model `none` fallback: connected second-pass outputs now return a valid clean main-model patcher with only the second-pass LoRA stack. External KJNodes receive a MODEL rather than None. Explicit second models and generic Loader opt-in behavior are preserved.
- Avoids eager second-pass preparation when the output is not connected; loads the Remix fallback only when the connected second-pass output needs it, then reuses the already loaded clean main-model base. Skips optional memory-feature clones when both switches are off.
- Reuses reference-image VAE encodings within one Setup context and its trigger/high-resolution rebuilds; changed media or reference dimensions get fresh encodings. Prompt text is still re-encoded for each rebuild.
- Logs wall times for media/model/VAE loading, LoRA preparation, reference VAE encoding and text encoding, plus conditioning shapes. Bridge errors report the actual input shape and suggest a compatible encoder or disabling the bridge; incompatible embeddings are not reshaped or silently accepted.
- Preserves RH API/authentication/billing, model/resource selectors, class IDs and widget/socket ordering.
- Validation: focused CPU/mock regressions, Python/JavaScript syntax and synchronized-file hashes. The repository's legacy production-pack removal test is incompatible with the current v1.4.10 production-pack source. No live RunningHub GPU timing or quality test was performed.

## v1.4.11

- Removes the standalone RH Dual Sample 1st/2nd nodes from the node menu. RH Sample Enhancer 1st/2nd remain available and continue to use their shared internal sampling implementation.

## v1.4.10

- Completes RH Setup and independent Media nodes (9 images / 3 videos / 3 audios), with direct JSON transport, file-aware caching, video/audio trim and preview, and connected-media prompt references. Preserves the original main-node widget/socket order.
- Adds shot-by-shot continuation and RH Continue Out (接续合并), using the existing external first/second-pass samplers rather than an internal competing sampler. Supports per-shot transition/frame settings, manual previous-video selection, and Video Combine V2 tail sidecars. Keeps the legacy production-plan output and packed-output class IDs for compatibility.
- Adds read-only H3 core capability probes and clone-scoped patch inventory diagnostics; retains downstream/third-party patches and does not install new attention algorithms.
- Expands face-refinement square canvas presets from 360P through 1080P, with H3 grid alignment and legacy 512/768 workflow validation.
- Retains RunningHub uploads, resource/model/LoRA selectors, RH LLM API, RH_OPENAPI_CONFIG, authentication and billing. Custom continuation/ZIP routes still require platform gateway/storage support.

- Intentionally does not synchronize no-reference-image production shots or HTML asset-path mapping. Standard-edition local unpublished changes remain untouched.
- Validation: focused CPU/mock regressions, Python/JavaScript syntax, baseline API/resource contract checks and source/installation SHA-256 synchronization. Live RunningHub GPU generation was not performed.

## v1.4.9

- Adds the RH-compatible Dual Sample and Sample Enhancer nodes, including the `Default Trigger Words` switch on both Sample Enhancer passes. It defaults on without exposing the trigger text in the node UI.
- Preserves RunningHub model/resource selectors, LLM API, authentication/billing checks and RH-specific node class IDs.
- The default trigger words are prepended to the encoded prompt only when enabled; the trigger text is not exposed in the node UI.
- Validation: Python/JavaScript syntax and source/installation synchronization; live RunningHub GPU generation was not performed.

## v1.4.8

- Removes the face-refinement 24 FPS restriction; uses the frame rate supplied by H3 context for existing timing calculations and output.
- No new controls, interpolation checks, or widget-order changes. Syntax and file synchronization verified; non-24-FPS GPU quality not re-tested.

## v1.4.7

- Checks standard linear LoRA dimensions before bypass loading. Skips incompatible layers with explicit warnings and matched/skipped counts; fails early when none are usable.
- Preserves RunningHub resource resolution, LLM API and authentication/billing, plus matching adapters and multi-LoRA composition. Other adapter types are delegated to ComfyUI with an unvalidated warning.
- No UI changes. CPU compatibility regressions tested; live RunningHub GPU execution not tested.

## v1.4.6

- Hides the LoRA bypass toggle and enables additive bypass consistently, including legacy regular-mode workflows and API inputs.
- Preserves RunningHub LoRA resource selectors, LLM API, authentication/billing, strengths, enable flags and widget order.
- Validated frontend migration, backend stack behavior, syntax and synchronized files. Live RunningHub GPU execution was not tested.

## v1.4.5

- Adds RH-specific experimental Face Refine, including original-audio conditioning, clean pre-LoRA second-pass model selection, automatic cropping of the first original reference image, and advanced-only controls.
- Adds the RH Production Pack Loader: folder/ZIP import, HTML discovery, preview, generation order and multiple independently trimmed reference audios. Routes, socket IDs and caches are isolated from the standard edition; existing origin/path/ZIP security checks are retained.
- Adds the main prompt input socket and preserves reference-video filenames during time trimming.
- Preserves RunningHub LLM API, authentication/billing checks and resource selectors. Platform-managed API settings are not replaced with desktop-provider settings.
- RunningHub must expose custom upload routes/storage and provide face-detector dependencies/weights. These capabilities cannot be guaranteed by the node package alone; see docs/rh-feature-parity.md.
- Validation: CPU import of all 11 RH nodes, seven production-route tests, 20-audio package materialization, mocked face-refinement pipeline, Python/JSON/frontend checks and saved-widget migration tests. No live RunningHub/GPU generation was performed.

## v1.4.4

- Adds reference-video time ranges and play/stop previews; video frames and source audio are cropped together with 100 ms input normalization.
- Replaces the automatic-duration toggle with Off / Reference audio / Reference video alignment, retaining legacy Boolean migration and stable widget ordering.
- Includes clone-safe sampling handoff/cache fixes, multi-LoRA regular/bypass selection, the standalone resolution selector, and the optional text-encoder-only reference mode.
- Preserves RunningHub LLM API/authentication/billing and resource selectors. Production-pack loading and experimental face refinement remain standard-only.
- Validation: Python/JavaScript syntax, JSON parsing, crop/playback simulations and saved-widget migration tests. Live RunningHub generation was not performed locally.

## v1.4.3

- Fixes complete streamed-block output-head compatibility with the updated ComfyUI 0.35 H3 calling convention, retaining native fallbacks.
- Adds optional streamed-block diagnostics and post-sampling cache cleanup, plus the RH Remix Loader with independent first/second-pass LoRA stacks.
- Improves modern-node sizing and prompt footer spacing while preserving frontend isolation and existing RH input ordering.
- Excludes the standard-only Production Pack Loader and development tests from the RH package.
- Preserves the RunningHub 260907 LLM API, authentication/billing checks and platform resource selectors. Standard-only sparse/text-only-reference experiments are not included.
- Validation: original RunningHub ZIP baseline checks, CPU wrapper tests and frontend checks passed. Live RunningHub generation was not performed locally.

## v1.4.2

- Integrates the RunningHub 260907 LLM API adaptation, preserving platform model selection, RH_OPENAPI_CONFIG, authentication and balance prechecks.
- Isolates RH frontend installation markers from standard Easy H3 and other H3 extensions; matches real node class IDs instead of titles/shared flags.
- Checks reference-media availability and unresolved references before prompt optimization or sampling, preserving RH resource loading and existing input order.
- Validation: original-baseline AST/file checks, CPU media-guard tests and both transport-wrapper orders. Live RunningHub LLM calls and full GPU generation were not performed locally.

## v1.4.1

- Fixes the RH prompt preview so it no longer exposes internal media filenames or unresolved reference markers; stale mention IDs now fall back to the current gallery order.
- Adds drag-to-reorder for embedded images, videos, and audio within their own media types.
- Adds a play/stop control beside each reference-audio trim range. Preview playback follows the normalized trim range and does not change the source file or the H3 audio payload.

## v1.4.0

- Adds **Digital human/MV auto duration**. When enabled, Audio 1's trimmed duration controls generation and locks the manual duration field.
- Adds **FeiHou Easy H3 Digital human/MV Duration Crop** and a matching `duration_control` output on FeiHou Easy H3 Output. H3 now rounds automatic-duration sampling up to its required `5 + 17N` frame count; the crop node restores the precise trimmed-audio duration after decoding, while passing ordinary workflows through unchanged.

## v1.3.12

- Adds per-slot **reference-audio trimming** below the embedded Audio 1–3 gallery. Start and end are separate fields; ranges are saved with their audio when reordered. Times accept forgiving input and normalize to 100ms precision (`MM:SS:MMM`); trimming affects only the temporary H3 audio payload, never the uploaded source file.
- Adds **CLIP** and trimmed **Audio 1** outputs to FeiHou Easy H3 Output. They are appended after existing outputs so saved workflow links keep their original slot positions.
- Aligns the reference-image **Match generation size** rule with the official H3 node's downscale-only output-pixel-area behavior. When an I2V/FL2V workflow actually requests second-pass sampling, its shared context now uses H3's reference-to-video latent representation.

## v1.3.11

- Fixes native ComfyUI external-input support for the embedded Easy H3 UI. Connected widgets now preserve their graph links instead of being overwritten by panel defaults during workflow serialization.
- The fix covers duration, resolution, aspect ratio, width/height, FPS, advanced settings, force offload, reference options, and prompt-optimizer controls. Embedded image/video/audio uploads and ordering are unchanged.

## v1.3.10

- Accepts legacy/display API-format values such as **OpenAI Compatible**, **OpenAI 兼容**, **Gemini 原生**, and **自动识别** in saved RunningHub workflows. Ollama now reports an explicit RH-not-supported message.
- Fixes the Loader text-encoder model list: the `text_encoders` category is now passed as a real one-item tuple, so all locally available encoder files are listed rather than only the fallback model.
- Fixes embedded prompt-editor bounds so the editor cannot extend beyond the node or cover the first native option row.
- Improves RH LoRA-strength editing: arrow controls respond immediately, number clicks accept direct input, and dragging remains available on the number area.

## v1.3.9

- Fixes prompt-guide titles to read ComfyUI's current locale at display time rather than locking in the language during frontend module initialization.
- Adds the missing Chinese/English fallback label for **R2VA 加强版 / R2VA Enhanced**, so the guide remains correctly named while the backend scheme list is loading or when frontend cache is refreshed.

## v1.3.8

- Removes filename-based REF2VA rejection in reference-video first and second sampling. In RunningHub, renamed community and Remix weights are accepted according to the Loader slot selected by the user instead of requiring `ref2va` in the resource filename.
- Adds the built-in **R2VA Enhanced** prompt guide directly below “General only”, using the supplied six-section full-reference prompt template for complex reference relationships.
- With **Force offload** enabled, releases a cached second-pass transformer from the prior workflow execution before preparing the next first-pass model, avoiding unnecessary concurrent VRAM use.

## v1.3.7

- Rebased the RH edition on RunningHub's current developer-compatible media workflow: embedded-media parameters, COS-backed media resolution, and RH resource model pickers are retained without desktop-only model-folder scanning.
- Adds optional second-pass sampling model output, explicit validation for second-pass wiring, and an option to skip LoRA during the second pass.
- Adds **Force offload**: after conditioning, CLIP, video/audio VAE and cached LoRA resources can be released before sampling to reduce VRAM pressure; the normal ComfyUI placement policy remains available when it is off.
- Improves the embedded 9-image / 3-video / 3-audio panel's responsive layout and prompt editor sizing.
- Keeps prompt-optimization media compact and portable: images and video keyframes are resized only for the API request, JPEG-encoded at quality 85, and diagnostic logs redact credentials and media contents.
- Removes an unused desktop-only settings script from the RH package. RH prompt API configuration remains entirely node-local.

## v1.3.1

- Fixes a route collision when the RH and standard editions are installed together. The RH prompt-editor button now calls its own in-node API endpoint instead of the standard edition's settings-based endpoint.

## v1.3.0

- Prompt optimization now sends API-only JPEG copies of reference images, capped by the node's selected `ref_image_size` and encoded at quality 85. Original H3 media is never modified.
- Reference videos now contribute compact first, middle, and last visual keyframes to compatible prompt-optimization APIs; standalone audio and video soundtracks remain local to H3 generation.
- Adds safe prompt-API diagnostics: logs include endpoint, model, API format, and media-size summaries while redacting API keys, filenames, Base64 payloads, and media contents.

## v1.2.0

- Removes filename-based filtering from the H3 Loader. Renamed community model files are now listed from their respective ComfyUI model folders.
- Lets users manually assign the selected diffusion model, text encoder, video VAE, and audio VAE to each H3 Loader role.
- Keeps `.safetensors` and `.gguf` discovery across the relevant ComfyUI model directories.

## v1.1.0

- Fixes an issue where ComfyUI serializing a Boolean as the string `"false"` could still incorrectly run the in-node prompt optimization.
- When prompt optimization is off, the node no longer makes an invalid API request or adds unnecessary waiting time.
- Improves compatibility with saved RunningHub workflows.

## v1.0.0

- Adds a visible `modified` declaration to the main node header, preserving the H3 source (`nkxx188/ComfyUI-MiniMaxH3-Easy`).
- Embeds up to 9 images, 3 videos, and 3 standalone audio files directly in the Easy H3 node.
- Adds the FeiHou LoRA Stack input flow for the Easy H3 Loader.
- Adds ComfyUI Settings integration for API providers, configured service/model selection, and prompt-optimization rules.
- Applies the selected prompt scheme during normal node execution, and carries the final result to H3 Context / Prompt Preview.

## Attribution

This release includes modified work derived from [nkxx188/ComfyUI-MiniMaxH3-Easy](https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy) (MIT). See [NOTICE](NOTICE), [LICENSE](LICENSE), and [LICENSES/MIT-ComfyUI-MiniMaxH3-Easy.txt](LICENSES/MIT-ComfyUI-MiniMaxH3-Easy.txt).
