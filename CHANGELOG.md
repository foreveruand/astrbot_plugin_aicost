# Changelog

## 1.1.0 - 2026-03-29

- 用 `Pillow` 直接绘制报告图片，移除对 `playwright` 和 Chromium 的依赖
- 卡片渲染改为按已启用 provider 动态聚合，不再固定显示 Gemini、Grok、OpenRouter
- 查询逻辑改为只执行已配置完成的 provider，减少无效网络请求
- 报告卡片新增对 Azure OpenAI 的动态展示支持
- 更新 `README.md`、`metadata.yaml` 和依赖说明
