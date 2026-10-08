# RH feature additions

## Setup and independent Media (v1.4.10)

`FeiHouEasyH3RHMedia` → `h3_media` → `FeiHouEasyH3RHSetup`; the Loader's bundle goes to Setup's `h3_bundle`. Setup's MODEL, second-pass MODEL and H3 Context remain in slots 0–2. The monolithic RH node remains available, with its original 22 serialized widget positions.

Media retains the supplied RH baseline's `api.fetchApi('/upload/image')` upload abstraction and RH extension registration. Files remain RH/ComfyUI input resources, not local desktop absolute paths or remote URLs. No full resource-directory scan or desktop provider configuration is added. RH model/LoRA popups and RH_OPENAPI_CONFIG, LLM authentication/billing are unchanged. Independent Media video/audio trims and preview feed Setup's automatic duration alignment and `@` prompt references; direct, reroute and KJ Set/Get links are supported.

External API clients may populate Media's `embedded_media_json` with an array of `{filename, subfolder, media_type, ordinal, audio_trim}` objects, or `media_N`, `media_type_N`, `media_trim_N` inputs (N=1..15). Use filenames already uploaded to the execution server's input directory. Connect Setup's `h3_media` to the Media output in prompt JSON. The output carries real resource records; it does not require the browser's graphToPrompt hook. Image/keyframe mode uses only the first two pictures; reference mode uses 9/3/3. Existing RH file existence and reference-media checks still apply.

## External-workflow continuation (v1.4.10)

Connect Production Pack Loader's `production_shot` (slot 0) to **both** RH Setup and `FeiHouEasyH3RHContinueOut`. Keep the existing first-pass and second-pass model/conditioning/latent/sampler chain. Connect the final H3 joint LATENT to Continue Out's `latent`, plus final images/audio when needed (for example after face refinement). `continue_from=latent` uses the sampled latent tail; `image` re-encodes the final pictures. Continue Out's images/audio/fps feed the video saver; its `tail_latent` feeds **FeiHou Toolbox Video Combine V2**'s latent input. V2's continuation-sidecar support is required for `.latent` saving and final full-video joining; an ordinary video saver only saves each trimmed segment.

The package loader controls shot transition (Auto/Continue/Cut), first+second-pass guide frames, batch-vs-manual mode and previous-video selection. There are no duplicate step/sampler/seed/upscale controls on Setup. Its frame choices match the current Standard implementation (5/22/39-frame H3 guides, with 0 disabling a pass). Saved-video restart continuation needs the preceding video/sidecar on the execution server. Memory/manifest/upload namespaces are RH-isolated. The legacy plan output (slot 1) and old Continuous unpacker class remain for saved links, but the obsolete internal Setup sampler is not used; migrate old internal-continuation workflows to this external chain.

Platform caveat: the custom `/feihou_easy_h3_rh/production_pack/*` routes and input/output storage must be permitted by RunningHub. The browser's continuation-file chooser does not bypass RH restrictions. If the gateway blocks custom uploads, use a server-side input/output path supplied by the platform; otherwise the platform operator must enable the routes. A static/mock check cannot certify live platform uploads or billing.

## Compatibility diagnostics and face-refinement canvas

Core probes run on tiny CPU sentinels; patch inventories are advisory and preserve third-party wrappers/attention patches. Diagnostics cannot guarantee every stacked algorithm is compatible and never conceal sampling exceptions. Face canvas presets are 360P, 416P, 480P, 540P, 640P, 720P, 768P, 832P, 928P, 1024P and 1080P; square edges align to the H3 32-pixel grid. Old 512/768 values remain valid. Larger face canvases may use more VRAM.

Explicitly excluded from this synchronization: production shots without reference pictures, and HTML asset-ID-to-file-path mapping. RH retains the original 1–9 image reference validation and ID-based asset lookup.

The RH package now includes RH-specific Production Pack Loader and experimental Face Refine nodes. Their Comfy class IDs, production-shot socket type, HTTP route prefix and package cache directory are distinct from the standard edition.

## Production packages

Folder/ZIP import, HTML discovery, shot preview, generation order and multiple reference audio tracks use the standard-edition implementation. Relative paths resolve under the server's ComfyUI/input. Existing request-origin checks, ZIP/path validation and remote directory restrictions remain active.

RunningHub must expose the custom /feihou_easy_h3_rh/production_pack endpoints and allow ZIP requests and server-side package storage. This implementation does not bypass the platform gateway. Installing the node alone cannot guarantee that RunningHub's website offers these capabilities. If upload is unavailable, the platform operator must enable it; local or self-hosted ComfyUI can use the node normally.

The server's API/authentication/billing and resource selectors are unchanged. Production-shot prompts do not disable enabled RH LLM billing checks. The main node's duration-alignment menu remains authoritative.

## Face refinement

See ../FACE_REFINE.md for optional dependencies, detector weights, clean second-pass model selection, original-audio conditioning and reference-face cropping. Dependencies/weights must be available on the execution server; this node does not install them automatically.

The clean second-pass model record is captured before applying second-pass LoRAs, with shared base weights. It cannot remove LoRAs baked into a model file. The first original reference image is retained as a CPU image for automatic face cropping.

Standard-only local API-provider settings are intentionally not copied over RH's platform API settings. This avoids replacing RunningHub authentication, billing or resource discovery.

CPU/mock and frontend checks do not constitute a live RunningHub integration test.
