# ComfyUI 0.35 compatibility and additive RH features

- Output-head streaming accepts old and new H3 argument contracts without allowing sigma to overwrite the captured layer. Small inputs and PDD head banks use the bound native implementation with all arguments preserved.
- The opt-in complete low-VRAM control also logs existing block/head patches. Force offload includes a sampler-return allocator cleanup, not a per-step cleanup.
- Remix uses RH UNET resource selectors and independent optional first/second LoRA stacks. Existing RH loader semantics and input ordering are preserved.
- The production-pack loader, its input socket, browser scripts and preparation endpoints have been removed from RH. This feature remains available only in the standard edition. Existing RH image/COS and RH_OPENAPI_CONFIG/LLM billing paths are retained.
- Prompt footer reserves 12 px; modern-node sizing retains a stable baseline. RH isolation markers remain distinct from standard and other H3 extensions.

CPU wrapper/transport/regression checks do not replace a full GPU or RunningHub cloud test. No release was published as part of this merge.
