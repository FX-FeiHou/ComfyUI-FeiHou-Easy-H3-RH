# ComfyUI-FeiHou-Easy-H3-RH

[English](README_EN.md) | **中文**

> **适用范围：这是面向 RunningHub（RH）的适配版。** 日常本地 ComfyUI 使用请优先选择标准版：[ComfyUI-FeiHou-Easy-H3](https://github.com/FX-FeiHou/ComfyUI-FeiHou-Easy-H3)。

这是用于 RunningHub 的 MiniMax H3 ComfyUI 节点包。它以 `ComfyUI-FeiHou-Easy-H3` 为基础，将参考媒体加载内嵌到主节点内。

主节点把参考媒体加载全部收进节点内部，不再需要外接 `Load Image`、`Load Video`、`Load Audio` 节点：

- 9 个图片槽位，固定 3 × 3 九宫格；
- 3 个视频槽位；
- 3 个独立音频槽位；
- 点击槽位选择文件，也可以把文件直接拖入槽位；
- 图片和视频在节点内预览，音频显示文件名；
- 已上传文件随工作流记录，重新打开工作流后仍可恢复；
- 参考模式继续支持在提示词里输入 `@` 选择 `<Picture i>`、`<Video i>`、`<Audio i>`；
- 视频原有音轨仍与该视频自动配对，3 个音频槽位作为独立参考音频；
- 默认 24 FPS、10 秒；参考图尺寸可选短边 480、544、640、736、768、832、928、1024、1088；
- 打开高级选项后可见“提示词优化设置”；开启后直接在节点内填写 API 地址、Key 与模型名，接口类型可自动识别，也可手动指定 OpenAI 兼容或 Gemini 原生；
- 保留内置提示词方案，不提供自定义方案、全局 API 设置页或 Ollama 选项；
- 保留 ✦ 点击反推、工作流运行时自动反推，以及 H3 Context 的最终提示词预览输出。

> **安全提示**：RH 版将 API Key 存在节点工作流参数中，导出或分享工作流前请清除 Key，或使用权限受限、可随时撤销的 Key。

## 节点

- `加载LoRA（旁路，仅模型）（用于调试）`：完全沿用 `FeiHou LoRA Stack (Merge/Extract)` 的原生画布堆栈样式，可动态添加、启停、排序多个 LoRA；
- `FeiHou Easy H3 Loader`：从左侧接收 LoRA 堆栈，并在内部加载 FL2VA/REF2VA 模型和应用 LoRA，同时加载文本编码器、视频 VAE 和音频 VAE；
- `ComfyUI-FeiHou-Easy-H3-RH`：主生成节点及内嵌媒体面板；
- `FeiHou Easy H3 Model Adapter`：接入外部标准 ComfyUI 模型加载链；
- `FeiHou Easy H3 Output`：拆出 Conditioning、Latent、视频 VAE、音频 VAE、FPS 和最终提示词；
- `FeiHou Easy H3 提示词预览`：显示 H3 Context 携带的最终扩写 / 反推提示词。

节点分类为 `FeiHou Easy H3`，类名使用独立的 `FeiHouEasyH3RH*` 前缀，可与原版 `ComfyUI-MiniMaxH3-Easy` 同时安装，不会发生节点 ID 或提示词优化路由冲突。

## 使用

1. 将 `ComfyUI-FeiHou-Easy-H3-RH` 整个文件夹放到 `ComfyUI/custom_nodes/`，保持该目录名。
2. 更新到包含官方 MiniMax H3 节点的新版 ComfyUI。
3. 重启 ComfyUI，并在 `FeiHou Easy H3` 分类中添加节点。
4. 把“加载LoRA（旁路，仅模型）（用于调试）”放在 Loader 左侧，将它的 `lora_stack` 输出接到 Loader 左侧的“LoRA 堆栈”输入；Loader 再连接主节点。LoRA 不再串联到主节点的 `model` 输出链路上。
5. 选择“参考生成视频”模式后，九宫格、3 个视频槽和 3 个音频槽都会启用。

提示词优化设置不使用 ComfyUI 的全局设置页。主节点关闭“高级选项”时不显示、也不执行提示词优化；打开后再开启“提示词优化设置”，即可直接在节点内填写 API 地址、API Key、模型名并选择内置提示词方案。接口类型默认为自动识别，也可按服务要求手动选择 OpenAI 兼容或 Gemini 原生。API Key 保存在工作流节点参数中，导出工作流前请自行清除。

开发时可自行维护本机的同步配置；本仓库不会提交本机路径、API Key、上传媒体或输出元数据。

在“图生或首尾帧”模式下，只使用九宫格前两个图片槽：一张图按高级选项作为首帧或尾帧，两张图作为首尾帧。切换模式不会删除已选的其他参考素材，返回参考模式后可继续使用。

## 媒体限制

- 参考图片：最多 9 张；
- 参考视频：最多 3 个；
- 独立参考音频：最多 3 个；
- 参考模式至少需要一张图片或一个视频，不能只提供音频；
- 视频帧和同步音轨的编码、排序及标签规则与 ComfyUI 官方 `MiniMax H3 Reference to Video` 节点一致。

## 改编、致谢与许可

本项目是改编版本，并非独立重写。H3 节点上游来源为 [nkxx188/ComfyUI-MiniMaxH3-Easy](https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy)，原作者为 `nkxx188`，采用 MIT License；其 MIT 文本和版权声明保留在 [LICENSES/MIT-ComfyUI-MiniMaxH3-Easy.txt](LICENSES/MIT-ComfyUI-MiniMaxH3-Easy.txt)。上游项目要求对实质性复用或改编保留作者与项目署名；本仓库已在节点头部、README、[NOTICE](NOTICE) 和 Release 中明确保留该声明。

FeiHou 的改动包括：固定 9 图 / 3 视频 / 3 音频的内嵌媒体面板、上传与工作流持久化、FeiHou LoRA Stack 接入、ComfyUI 设置页内的 API 与提示词规则管理、服务/模型选择、运行时提示词扩写/反推，以及提示词预览输出。参考素材的 conditioning 规则及数量限制仍遵循 ComfyUI 官方 `MiniMax H3 Reference to Video` 行为。

完整许可证和保留声明见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。软件按“现状”提供，不附带任何担保。
