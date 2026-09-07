# RH 260907 基线与前端隔离修复

本地 RH 版以用户提供的 `ComfyUI-FeiHou-Easy-H3-RH-rh-develop-260907.zip` 为基线，原 ZIP 和旧 rh-develop 目录不修改。

只补充两类修复：

- 将共用安装/监听标记改为 RH 独立的 `__feihouRHH3*` 前缀；只按真实 RH 节点类名匹配，不按标题或其他插件的安装标记认领节点。与标准版标记也独立。
- 在参考模式调用付费提示词优化之前检查是否存在图片/视频，并拒绝未解析的 `__MINIMAX_H3_UNRESOLVED_REF_*`。保留 RH 原有空媒体报错和媒体回退读取逻辑。

RunningHub 提供的 `rh_llm.py`、LLM 模型列表、`api_config` 接口、平台鉴权/余额预检查、API 请求参数以及资源选择器保持原样；没有引入标准版制作包功能，没有改变已有控件保存顺序。

已完成语法检查、两种补丁处理顺序的传输模拟及与原 ZIP 的代码结构比较。除新增保护函数和调用之外，`nodes.py` 原有语法树完全一致；除 `nodes.py` 和主前端 JS 之外，ZIP 原有文件逐字节保持一致。

本地未安装 `ComfyUI_RH_OpenAPI` 时不能使用 RH 平台 LLM 调用；此依赖来自 RunningHub 提供的版本。本次没有进行云端付费 API 或完整 GPU 视频生成测试。

更新后重启 ComfyUI，并关闭旧页面重新打开或 Ctrl+Shift+R 硬刷新，以清除旧前端补丁。云端平台需要部署新版代码后重新测试。

## English

Based on the user-supplied RH 260907 ZIP. Only RH-specific frontend ownership/isolation and early reference-media validation were added. RunningHub LLM integration and existing input order are preserved. Syntax, baseline-AST, unchanged-file and transport-order tests passed; no paid cloud API or end-to-end GPU test was performed. Restart ComfyUI and fully reload the browser after updating.
