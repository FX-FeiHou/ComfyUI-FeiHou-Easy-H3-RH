# ComfyUI-FeiHou-Easy-H3-RH

[中文](README.md) | **English**

> **Scope:** This is the RunningHub (RH) compatibility edition. For ordinary local ComfyUI use, prefer the standard edition: [ComfyUI-FeiHou-Easy-H3](https://github.com/FX-FeiHou/ComfyUI-FeiHou-Easy-H3).

A RunningHub-oriented MiniMax H3 custom-node package based on `ComfyUI-FeiHou-Easy-H3`, with all reference-media loading embedded directly in the main node.

The main node provides:

- nine image slots in a fixed 3 × 3 gallery;
- three video slots;
- three standalone audio slots;
- click-to-pick and drag-and-drop upload;
- inline image/video previews and persistent workflow metadata;
- the original `@` reference editor for `<Picture i>`, `<Video i>`, and `<Audio i>`;
- default 24 FPS and 10-second generation;
- reference-image short-edge presets of 480, 544, 640, 736, 768, 832, 928, 1024, and 1088;
- direct node-level prompt-optimizer settings with automatic API detection, plus OpenAI-compatible and native Gemini overrides;
- bundled prompt guides only (no user-defined prompt schemes or global API settings page).

In the RH build, enable Advanced options and then Prompt optimization settings to enter the API URL, key, and model directly on the node. The API type is detected automatically by default, with OpenAI-compatible and native Gemini overrides when needed. Only bundled prompt guides remain; Ollama and global API/settings pages are not included. The ✦ action, runtime prompt optimization, and H3 Context prompt-preview output are retained.

> **Security notice:** API keys are saved in workflow node parameters in this RH build. Clear keys before exporting or sharing workflows, or use restricted and revocable keys.

Video soundtracks remain paired with their source videos. The three audio slots are standalone audio references. In image/first-last-frame mode, only the first two image slots are active; switching modes preserves the remaining gallery selections.

## Install

Copy the `ComfyUI-FeiHou-Easy-H3-RH` folder into `ComfyUI/custom_nodes/` and keep that directory name, update ComfyUI to a release that includes the official MiniMax H3 nodes, and restart ComfyUI.

Nodes appear under `FeiHou Easy H3`:

- `加载LoRA（旁路，仅模型）（用于调试）` (the same native canvas stack UI as `FeiHou LoRA Stack (Merge/Extract)`)
- `FeiHou Easy H3 Loader`
- `ComfyUI-FeiHou-Easy-H3-RH`
- `FeiHou Easy H3 Model Adapter`
- `FeiHou Easy H3 Output`
- `FeiHou Easy H3 Prompt Preview`

Place the LoRA stack to the left of `FeiHou Easy H3 Loader` and connect its `lora_stack` output to the loader's left-side `LoRA stack` input. The loader applies every enabled LoRA internally; the LoRA node is not inserted into the main node's downstream `MODEL` chain.

Prompt optimization does not use a global ComfyUI Settings page in this edition. The main node shows no optimizer controls until Advanced options is enabled; then enable Prompt optimization settings to enter the API URL, key, model, and bundled prompt guide directly on the node. API type defaults to automatic detection and can be overridden to OpenAI-compatible or native Gemini. API keys are saved in workflow node parameters, so clear them before sharing a workflow. The final prompt is carried in H3 Context and can be connected from `FeiHou Easy H3 Output` to the bundled Prompt Preview node.

The package uses unique `FeiHouEasyH3RH*` node IDs and dedicated prompt-optimizer routes, so it can be installed alongside the original project.

## Attribution, changes, and license

This is a **modified work**, not an independent reimplementation. Its H3-node upstream source is [ComfyUI-MiniMaxH3-Easy](https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy) by `nkxx188`, which is MIT-licensed. Its original copyright notice and MIT text are retained in [LICENSES/MIT-ComfyUI-MiniMaxH3-Easy.txt](LICENSES/MIT-ComfyUI-MiniMaxH3-Easy.txt). The original project asks substantial reuses/adaptations to credit `nkxx188` and `ComfyUI-MiniMaxH3-Easy`; this repository does so in the node header, this README, [NOTICE](NOTICE), and every release.

The API-service configuration, model-discovery, and prompt-optimization implementation borrows from [yawiii/ComfyUI-Prompt-Assistant](https://github.com/yawiii/ComfyUI-Prompt-Assistant) by `yawiii`, which is GNU GPL v3-licensed. Because this repository includes adapted portions of that project, the repository as a whole is distributed under the [GNU GPL v3](LICENSE).

FeiHou-specific changes include the fixed 9-image / 3-video / 3-audio embedded gallery, gallery upload/persistence, FeiHou LoRA Stack integration, settings-page API and prompt-rule management, configured service/model selection, runtime prompt optimization, and prompt-preview outputs. Reference conditioning follows ComfyUI's official `MiniMax H3 Reference to Video` behavior and limits: 9 images, 3 videos, and 3 standalone audio clips.

The complete license and preservation notice are in [LICENSE](LICENSE) and [NOTICE](NOTICE). The software is provided as-is, without warranty.
