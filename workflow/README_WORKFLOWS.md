# FeiHou Easy H3 工作流说明

## 中文说明

使用本文件夹中的工作流前，请先安装所需插件，并下载对应模型。

> RunningHub 版的提示词优化 API 在 `ComfyUI-FeiHou-Easy-H3-RH` 主节点内配置：先打开“高级选项”，再打开“提示词优化设置”，即可填写 API 格式、地址、Key 和模型名。示例工作流默认不启用优化，也不含任何 API Key。

### 可能需要安装的插件

- `ComfyUI-FeiHou-Easy-H3-RH`（本目录对应的 RunningHub 节点包）
- [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)
- [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)

也可以在 ComfyUI Manager 中搜索插件名称安装。安装或更新后请重启 ComfyUI。

### 模型与资源

工作流需要的插件、模型和相关资源：

小肥猴的网盘：<https://pan.quark.cn/s/27fe4727197b>

不同工作流需要的模型可能不同，请按照工作流中的加载器选择对应文件。如果列表中找不到模型，请检查模型是否放入了正确的 `ComfyUI/models` 子目录，然后刷新或重启 ComfyUI。

部分工作流还需要额外的 LoRA 或其他自定义节点，具体以工作流中的节点为准。

---

# FeiHou Easy H3 Workflow Guide

## English

Before using any workflow in this folder, install the required custom nodes and download the models used by that workflow.

> In the RunningHub build, configure prompt optimization directly on the `ComfyUI-FeiHou-Easy-H3-RH` main node: enable Advanced options, then Prompt optimization settings, and enter the API format, URL, key, and model. The example workflow is disabled by default and contains no API key.

### Required custom nodes

- `ComfyUI-FeiHou-Easy-H3-RH` (this RunningHub custom-node package)
- [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)
- [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)

You can also install them by searching for their names in ComfyUI Manager. Restart ComfyUI after installing or updating custom nodes.

### Models and assets

The plugins, models, and related assets used by the workflows are available here:

Xiao Fei Hou's cloud drive: <https://pan.quark.cn/s/27fe4727197b>

Model requirements may differ between workflows. Select the matching files in each workflow's loader node. If a model is not listed, place it in the correct `ComfyUI/models` subdirectory, then refresh or restart ComfyUI.

Some workflows may also require additional LoRAs or custom nodes. Please check the nodes included in the workflow.
