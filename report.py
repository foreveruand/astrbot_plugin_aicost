"""
HTML report generation for AI Cost Monitor.
"""

from datetime import datetime


def format_number(num: float) -> str:
    """Format large numbers, e.g., 12345 -> 12.3k."""
    if num >= 1000000:
        return f"{num / 1000000:.2f}M"
    if num >= 1000:
        return f"{num / 1000:.1f}k"
    return str(int(num))


def generate_html_report(
    google_data: dict,
    xai_data: dict,
    openrouter_data: dict,
) -> str:
    """Generate HTML report for AI service costs."""

    def render_card_content(data: dict, card_type: str) -> str:
        if not data.get("success"):
            return f'<div class="status-error">⚠️ {data.get("error", "Error")}</div>'

        if card_type == "google":
            models_html = ""
            for m in data.get("models", [])[:8]:
                models_html += f"""
                <div class="model-group">
                    <div class="model-header">
                        <span class="model-name">{m["model"]}</span>
                        <span class="model-total">${m["total_cost"]:.4f}</span>
                    </div>
                    <div class="token-info-line">
                        <span class="token-item">IN: <b>{format_number(m["input_tokens"])}</b> <small>(${m["input_cost"]:.4f})</small></span>
                        <span class="sep">|</span>
                        <span class="token-item">OUT: <b>{format_number(m["output_tokens"])}</b> <small>(${m["output_cost"]:.4f})</small></span>
                    </div>
                </div>"""
            return f'<div class="main-cost google-text"><span class="currency">$</span>{data["total_cost"]:.4f}</div><div class="detail-list">{models_html}</div>'

        elif card_type == "xai":
            models_html = "".join(
                [
                    f'<div class="model-row"><span class="model-name">{m["model"]}</span><span class="model-price">${m["cost"]:.3f}</span></div>'
                    for m in data.get("models", [])[:5]
                ]
            )
            return f"""
            <div class="main-cost xai-text">
                <span class="currency">$</span>{data["total_cost"]:.2f}
                <span class="sub-balance">BAL: ${data["balance"]:.2f}</span>
            </div>
            <div class="detail-list">{models_html}</div>"""

        elif card_type == "openrouter":
            return f"""
            <div class="main-cost or-text"><span class="currency">$</span>{data["remaining"]:.2f}</div>
            <div class="progress-section">
                <div class="progress-info"><span>Usage</span><span>{data["usage_percent"]:.1f}%</span></div>
                <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: {data["usage_percent"]}%"></div></div>
            </div>
            <div class="quick-stats">
                <div class="q-stat"><span>Used</span><strong>${data["used"]:.1f}</strong></div>
                <div class="q-stat"><span>Total</span><strong>${data["total"]:.1f}</strong></div>
            </div>"""

        return ""

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        :root {{
            --bg: #0b0f1a; --card-bg: #161c2d; --border: rgba(255, 255, 255, 0.08);
            --azure: #3b82f6; --google: #10b981; --xai: #f59e0b; --or: #ef4444;
            --text-main: #f1f5f9; --text-dim: #64748b;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', system-ui, sans-serif; }}
        body {{ background: var(--bg); color: var(--text-main); padding: 20px; width: 720px; }}

        .header {{ margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ font-size: 20px; color: var(--text-main); opacity: 0.9; }}

        .dashboard-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}

        .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 15px; display: flex; flex-direction: column; }}
        .card-header {{ font-size: 10px; font-weight: 800; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px; display: flex; align-items: center; gap: 5px; }}
        .card-header::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; }}
        .card.google .card-header::before {{ background: var(--google); }}
        .card.xai .card-header::before {{ background: var(--xai); }}
        .card.or .card-header::before {{ background: var(--or); }}

        .main-cost {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; display: flex; align-items: baseline; font-family: 'Consolas', monospace; }}
        .sub-balance {{ font-size: 11px; margin-left: auto; color: var(--text-dim); font-weight: 400; background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px; }}

        .google-text {{ color: var(--google); }} .xai-text {{ color: var(--xai); }} .or-text {{ color: var(--or); }}

        .detail-list {{ display: flex; flex-direction: column; gap: 4px; }}
        .model-row {{ display: flex; justify-content: space-between; font-size: 11px; padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.02); }}
        .model-name {{ color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 140px; }}

        .model-group {{ background: rgba(0,0,0,0.15); border-radius: 6px; padding: 6px 8px; margin-bottom: 2px; }}
        .model-header {{ display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 11px; font-weight: 600; }}
        .token-info-line {{ font-size: 9px; color: var(--text-dim); display: flex; gap: 6px; align-items: center; white-space: nowrap; }}
        .token-info-line b {{ color: #cbd5e1; }}
        .token-info-line small {{ opacity: 0.7; }}
        .sep {{ opacity: 0.2; }}

        .quick-stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: auto; padding-top: 10px; }}
        .q-stat {{ background: rgba(255,255,255,0.03); padding: 6px; border-radius: 6px; text-align: center; }}
        .q-stat span {{ display: block; font-size: 8px; color: var(--text-dim); text-transform: uppercase; }}
        .q-stat strong {{ font-size: 12px; }}

        .progress-bar-bg {{ background: rgba(255,255,255,0.05); height: 3px; border-radius: 2px; margin: 5px 0; }}
        .progress-bar-fill {{ background: var(--or); height: 100%; border-radius: 2px; }}
        .progress-info {{ display: flex; justify-content: space-between; font-size: 10px; color: var(--text-dim); }}

        .status-error {{ color: #ef4444; font-size: 11px; padding: 8px; text-align: center; }}
    </style>
</head>
<body>
    <div class="header"><h1>AI COST MONITOR</h1><p style="font-size:10px; color:var(--text-dim)">{datetime.now().strftime("%Y-%m-%d %H:%M")}</p></div>
    <div class="dashboard-grid">
        <div class="card google"><div class="card-header">Google Gemini</div>{render_card_content(google_data, "google")}</div>
        <div class="card xai"><div class="card-header">xAI Grok</div>{render_card_content(xai_data, "xai")}</div>
        <div class="card or"><div class="card-header">OpenRouter</div>{render_card_content(openrouter_data, "openrouter")}</div>
    </div>
</body>
</html>
    """


async def html_to_image(html_content: str) -> bytes:
    """Convert HTML content to image using Playwright."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 720, "height": 200})
            await page.set_content(html_content)
            await page.wait_for_load_state("networkidle")
            screenshot = await page.screenshot(full_page=True)
            await browser.close()
            return screenshot
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )
