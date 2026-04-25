"""
Report data builder for AI Cost Monitor.
Converts provider cost data into template variables for AstrBot's html_render.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

PROVIDER_THEMES = {
    "azure": {"accent": "#3b82f6"},
    "google": {"accent": "#10b981"},
    "xai": {"accent": "#f59e0b"},
    "openrouter": {"accent": "#ef4444"},
}

STYLES = {
    "midnight": {
        "name": "Midnight Grid",
        "bg": "#0b0f1a",
        "panel": "#161c2d",
        "panel_alt": "#101827",
        "soft_panel": "#1d2536",
        "border": "#2a3448",
        "text_main": "#f1f5f9",
        "text_dim": "#94a3b8",
        "text_muted": "#64748b",
        "error": "#ef4444",
        "progress_bg": "#20293b",
    },
    "paper": {
        "name": "Paper Ledger",
        "bg": "#f4efe6",
        "panel": "#fffaf0",
        "panel_alt": "#f6efe1",
        "soft_panel": "#ede4d3",
        "border": "#d9ccb6",
        "text_main": "#2f241a",
        "text_dim": "#6f604f",
        "text_muted": "#9b8b77",
        "error": "#c2410c",
        "progress_bg": "#e4d9c6",
    },
    "aurora": {
        "name": "Aurora Pulse",
        "bg": "#06151a",
        "panel": "#0d2328",
        "panel_alt": "#112d33",
        "soft_panel": "#16353c",
        "border": "#28505a",
        "text_main": "#e7fff8",
        "text_dim": "#9fcfc4",
        "text_muted": "#5f9589",
        "error": "#ff7a59",
        "progress_bg": "#21464f",
    },
}


def get_report_style_options() -> list[tuple[str, str]]:
    """Return available report styles for config UIs."""
    return [(style_id, style["name"]) for style_id, style in STYLES.items()]


def _resolve_style(style_id: str | None) -> dict:
    if style_id and style_id in STYLES:
        return STYLES[style_id]
    return STYLES["midnight"]


def _estimate_card_height(card: dict) -> int:
    data = card.get("data", {})
    if not data.get("success"):
        return 92

    card_id = card.get("id")
    if card_id == "openrouter":
        return 186
    if card_id == "google":
        model_count = min(len(data.get("models", [])), 8)
        warning_height = 17 if data.get("warning") else 0
        return 123 + model_count * 54 + warning_height
    if card_id == "xai":
        model_count = min(len(data.get("models", [])), 5)
        warning_height = 17 if data.get("warning") else 0
        return 107 + model_count * 45 + warning_height
    if card_id == "azure":
        model_count = min(len(data.get("models", [])), 6)
        return 123 + model_count * 45

    return 92


def _estimate_canvas_height(cards: list[dict]) -> int:
    body_padding = 76
    header_height = 48
    header_margin = 28
    tallest_card = max((_estimate_card_height(card) for card in cards), default=92)
    return body_padding + header_height + header_margin + tallest_card


def build_report_template_data(
    provider_cards: list[dict],
    style_id: str = "midnight",
) -> dict:
    """Build the Jinja2 template data dict for the cost report.

    Returns a dict suitable for passing to AstrBot's html_render / render_custom_template.
    """
    if not provider_cards:
        raise RuntimeError(
            "No provider modules are enabled. Please configure at least one provider."
        )

    style = _resolve_style(style_id)
    columns = min(3, len(provider_cards))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    cards = [
        {
            "id": card["id"],
            "name": card["name"],
            "accent": PROVIDER_THEMES.get(card["id"], {}).get("accent", "#888888"),
            "data": card["data"],
        }
        for card in provider_cards
    ]

    return {
        "style": style,
        "columns": columns,
        "timestamp": timestamp,
        "cards": cards,
        "canvas_height": _estimate_canvas_height(cards),
    }


def load_report_template(plugin_dir: str) -> str:
    """Load the Jinja2 HTML template from the plugin's resource directory."""
    tmpl_path = Path(plugin_dir) / "resource" / "report.html"
    return tmpl_path.read_text(encoding="utf-8")
