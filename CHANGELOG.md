# Changelog

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
