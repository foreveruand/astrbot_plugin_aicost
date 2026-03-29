# Changelog

## 1.2.0 - 2026-03-29

- 修复 Gemini 卡片主金额显示为 `USD` 而非美元符号的问题，统一所有 provider 的金额风格
- 修复 Gemini 模型项中 `IN` 与 `OUT` 信息横向重叠的问题，改为上下两行显示
- 新增 `report_style` 配置项，支持 `midnight`、`paper`、`aurora` 三种报告样式
- 新增 `resource/` 预览图资源，并在 `README.md` 中展示样式预览
- 收紧图片排版与数值格式，金额统一保留两位小数，token 统一按 `M` 显示两位小数，并尽量让 Gemini 的 `IN/OUT` 回到同一行

## 1.1.0 - 2026-03-29

- 用 `Pillow` 直接绘制报告图片，移除对 `playwright` 和 Chromium 的依赖
- 卡片渲染改为按已启用 provider 动态聚合，不再固定显示 Gemini、Grok、OpenRouter
- 查询逻辑改为只执行已配置完成的 provider，减少无效网络请求
- 报告卡片新增对 Azure OpenAI 的动态展示支持
- 更新 `README.md`、`metadata.yaml` 和依赖说明
