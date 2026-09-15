# RH feature additions

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
