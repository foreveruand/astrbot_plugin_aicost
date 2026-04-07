# Changelog


## 1.3.2 - 2026-04-07

- Fix duplicate "AI Cost Daily Report" cron job creation on plugin reload/restart
- Add job deduplication logic: delete existing job before registering new one
- Reference: same pattern used in astrbot_plugin_airss scheduler

## 1.3.1 - 2026-04-05

- 改用 AstrBot 原生的 HTML 渲染管线（`html_render` / t2i），移除基于 `Pillow` 的自定义绘制逻辑。
- 新增 Jinja2 模板 `resource/report.html` 与数据构建器 `report.build_report_template_data()`，通过模板渲染生成报告图片。
- 发送逻辑改为使用图片 URL（`Image.fromURL`），兼容 AstrBot 的 t2i 渲染返回；不再直接构造图片字节。
- 从配置中移除 `report_scale` 与 `report_font_file`（Pillow 专用），并已从 `requirements.txt` 中移除 `Pillow` 依赖。
- 如需自定义字体或输出清晰度，请使用 AstrBot 的 t2i 渲染端点/全局模板配置或运行本地 t2i 服务。

## 1.3.0 - 2026-03-29

- 新增 `report_font_file` 配置，支持上传 `ttf`、`otf`、`ttc` 作为报告自定义字体
- 新增 `report_scale` 配置，支持提高图片渲染倍率以获得更清晰输出
- 调整绘制尺寸与间距，在更高清输出下保持卡片排版清晰

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
