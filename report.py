"""
Image report generation for AI Cost Monitor.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from math import ceil

from PIL import Image, ImageDraw, ImageFont

CARD_WIDTH = 220
CARD_MIN_HEIGHT = 220
PADDING = 20
GAP = 12
HEADER_HEIGHT = 56

THEMES = {
    "azure": {"class": "azure", "accent": "#3b82f6"},
    "google": {"class": "google", "accent": "#10b981"},
    "xai": {"class": "xai", "accent": "#f59e0b"},
    "openrouter": {"class": "or", "accent": "#ef4444"},
}

COLORS = {
    "bg": "#0b0f1a",
    "card_bg": "#161c2d",
    "border": "#2a3448",
    "text_main": "#f1f5f9",
    "text_dim": "#94a3b8",
    "text_muted": "#64748b",
    "error": "#ef4444",
}


def format_number(num: float) -> str:
    """Format large numbers, e.g., 12345 -> 12.3k."""
    if num >= 1000000:
        return f"{num / 1000000:.2f}M"
    if num >= 1000:
        return f"{num / 1000:.1f}k"
    return str(int(num))


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_H1 = _load_font(22, bold=True)
FONT_TIME = _load_font(11)
FONT_CARD_TITLE = _load_font(11, bold=True)
FONT_VALUE = _load_font(28, bold=True)
FONT_BODY = _load_font(11)
FONT_BODY_BOLD = _load_font(11, bold=True)
FONT_SMALL = _load_font(9)
FONT_SMALL_BOLD = _load_font(9, bold=True)


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill: str):
    draw.text(xy, text, font=font, fill=fill)


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _truncate(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if _measure(draw, text, font)[0] <= max_width:
        return text
    suffix = "..."
    for end in range(len(text) - 1, 0, -1):
        candidate = text[:end] + suffix
        if _measure(draw, candidate, font)[0] <= max_width:
            return candidate
    return suffix


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _measure(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _estimate_card_height(draw: ImageDraw.ImageDraw, provider_id: str, data: dict) -> int:
    if not data.get("success"):
        lines = _wrap_text(draw, f'ERROR: {data.get("error", "Error")}', FONT_BODY, CARD_WIDTH - 40)
        return max(CARD_MIN_HEIGHT, 92 + len(lines) * 16)

    if provider_id == "google":
        count = min(len(data.get("models", [])), 8)
        return max(CARD_MIN_HEIGHT, 92 + count * 44)
    if provider_id == "xai":
        count = min(len(data.get("models", [])), 5)
        return max(CARD_MIN_HEIGHT, 120 + count * 22)
    if provider_id == "azure":
        count = min(len(data.get("models", [])), 6)
        return max(CARD_MIN_HEIGHT, 104 + count * 22)
    return CARD_MIN_HEIGHT


def _draw_card_header(draw: ImageDraw.ImageDraw, x: int, y: int, title: str, accent: str) -> int:
    draw.ellipse((x, y + 4, x + 6, y + 10), fill=accent)
    _text(draw, (x + 14, y), title.upper(), FONT_CARD_TITLE, COLORS["text_muted"])
    return y + 24


def _draw_error(draw: ImageDraw.ImageDraw, x: int, y: int, data: dict) -> int:
    lines = _wrap_text(draw, f'ERROR: {data.get("error", "Error")}', FONT_BODY, CARD_WIDTH - 40)
    for line in lines:
        _text(draw, (x, y), line, FONT_BODY, COLORS["error"])
        y += 16
    return y


def _draw_openrouter_card(draw: ImageDraw.ImageDraw, x: int, y: int, data: dict, accent: str) -> None:
    _text(draw, (x, y), f"${data['remaining']:.2f}", FONT_VALUE, accent)
    y += 42
    _text(draw, (x, y), "Usage", FONT_BODY, COLORS["text_dim"])
    usage = f"{data['usage_percent']:.1f}%"
    usage_width, _ = _measure(draw, usage, FONT_BODY)
    _text(draw, (x + CARD_WIDTH - 40 - usage_width, y), usage, FONT_BODY, COLORS["text_dim"])
    y += 18
    bar_x0 = x
    bar_y0 = y
    bar_x1 = x + CARD_WIDTH - 40
    bar_y1 = y + 6
    draw.rounded_rectangle((bar_x0, bar_y0, bar_x1, bar_y1), radius=3, fill="#20293b")
    fill_width = int((bar_x1 - bar_x0) * min(max(data["usage_percent"], 0), 100) / 100)
    if fill_width > 0:
        draw.rounded_rectangle((bar_x0, bar_y0, bar_x0 + fill_width, bar_y1), radius=3, fill=accent)
    y += 24
    stat_width = (CARD_WIDTH - 48) // 2
    for idx, (label, value) in enumerate((("Used", f"${data['used']:.1f}"), ("Total", f"${data['total']:.1f}"))):
        sx = x + idx * (stat_width + 8)
        draw.rounded_rectangle((sx, y, sx + stat_width, y + 46), radius=8, fill="#1d2536", outline=COLORS["border"])
        _text(draw, (sx + 10, y + 8), label.upper(), FONT_SMALL, COLORS["text_muted"])
        _text(draw, (sx + 10, y + 24), value, FONT_BODY_BOLD, COLORS["text_main"])


def _draw_xai_card(draw: ImageDraw.ImageDraw, x: int, y: int, data: dict, accent: str) -> None:
    _text(draw, (x, y), f"${data['total_cost']:.2f}", FONT_VALUE, accent)
    balance = f"BAL: ${data['balance']:.2f}"
    balance_width, _ = _measure(draw, balance, FONT_SMALL)
    badge_x = x + CARD_WIDTH - 48 - balance_width
    draw.rounded_rectangle((badge_x - 8, y + 8, x + CARD_WIDTH - 40, y + 28), radius=6, fill="#1d2536")
    _text(draw, (badge_x - 2, y + 12), balance, FONT_SMALL, COLORS["text_dim"])
    y += 48
    for model in data.get("models", [])[:5]:
        name = _truncate(draw, model["model"], FONT_BODY, CARD_WIDTH - 100)
        _text(draw, (x, y), name, FONT_BODY, COLORS["text_dim"])
        price = f"${model['cost']:.3f}"
        price_width, _ = _measure(draw, price, FONT_BODY)
        _text(draw, (x + CARD_WIDTH - 40 - price_width, y), price, FONT_BODY, COLORS["text_main"])
        y += 20
    if data.get("warning"):
        _text(draw, (x, y + 2), _truncate(draw, data["warning"], FONT_SMALL, CARD_WIDTH - 40), FONT_SMALL, COLORS["text_muted"])


def _draw_azure_card(draw: ImageDraw.ImageDraw, x: int, y: int, data: dict, accent: str) -> None:
    currency = data.get("currency", "USD")
    _text(draw, (x, y), f"{currency} {data['total_cost']:.2f}", FONT_VALUE, accent)
    y += 48
    for model in data.get("models", [])[:6]:
        name = _truncate(draw, model["model"], FONT_BODY, CARD_WIDTH - 95)
        _text(draw, (x, y), name, FONT_BODY, COLORS["text_dim"])
        price = f"${model['cost']:.4f}"
        price_width, _ = _measure(draw, price, FONT_BODY)
        _text(draw, (x + CARD_WIDTH - 40 - price_width, y), price, FONT_BODY, COLORS["text_main"])
        y += 20


def _draw_google_card(draw: ImageDraw.ImageDraw, x: int, y: int, data: dict, accent: str) -> None:
    currency = data.get("currency", "USD")
    _text(draw, (x, y), f"{currency} {data['total_cost']:.4f}", FONT_VALUE, accent)
    y += 48
    for model in data.get("models", [])[:8]:
        box_y1 = y + 36
        draw.rounded_rectangle((x, y, x + CARD_WIDTH - 40, box_y1), radius=8, fill="#101827", outline=COLORS["border"])
        name = _truncate(draw, model["model"], FONT_BODY_BOLD, CARD_WIDTH - 120)
        _text(draw, (x + 8, y + 6), name, FONT_BODY_BOLD, COLORS["text_main"])
        total = f"${model['total_cost']:.4f}"
        total_width, _ = _measure(draw, total, FONT_BODY_BOLD)
        _text(draw, (x + CARD_WIDTH - 48 - total_width, y + 6), total, FONT_BODY_BOLD, COLORS["text_main"])
        token_line = f"IN {format_number(model['input_tokens'])} (${model['input_cost']:.4f})"
        token_line_2 = f"OUT {format_number(model['output_tokens'])} (${model['output_cost']:.4f})"
        _text(draw, (x + 8, y + 22), token_line, FONT_SMALL, COLORS["text_dim"])
        out_width, _ = _measure(draw, token_line_2, FONT_SMALL)
        _text(draw, (x + CARD_WIDTH - 48 - out_width, y + 22), token_line_2, FONT_SMALL, COLORS["text_dim"])
        y += 42
    if data.get("warning"):
        _text(draw, (x, y + 2), _truncate(draw, data["warning"], FONT_SMALL, CARD_WIDTH - 40), FONT_SMALL, COLORS["text_muted"])


def generate_report_image(provider_cards: list[dict]) -> bytes:
    """Generate the cost report as PNG image bytes."""
    if not provider_cards:
        raise RuntimeError("No provider modules are enabled. Please configure at least one provider.")

    columns = min(3, len(provider_cards))
    rows = ceil(len(provider_cards) / columns)

    measure_image = Image.new("RGB", (CARD_WIDTH, CARD_MIN_HEIGHT), COLORS["bg"])
    measure_draw = ImageDraw.Draw(measure_image)
    heights = [_estimate_card_height(measure_draw, card["id"], card["data"]) for card in provider_cards]
    row_heights = []
    for row in range(rows):
        start = row * columns
        row_heights.append(max(heights[start : start + columns]))

    width = PADDING * 2 + columns * CARD_WIDTH + (columns - 1) * GAP
    height = PADDING * 2 + HEADER_HEIGHT + sum(row_heights) + (rows - 1) * GAP

    image = Image.new("RGB", (width, height), COLORS["bg"])
    draw = ImageDraw.Draw(image)

    _text(draw, (PADDING, PADDING), "AI COST MONITOR", FONT_H1, COLORS["text_main"])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    ts_width, _ = _measure(draw, timestamp, FONT_TIME)
    _text(draw, (width - PADDING - ts_width, PADDING + 8), timestamp, FONT_TIME, COLORS["text_muted"])

    y = PADDING + HEADER_HEIGHT
    for row in range(rows):
        x = PADDING
        row_cards = provider_cards[row * columns : (row + 1) * columns]
        row_height = row_heights[row]
        for card in row_cards:
            theme = THEMES[card["id"]]
            draw.rounded_rectangle(
                (x, y, x + CARD_WIDTH, y + row_height),
                radius=14,
                fill=COLORS["card_bg"],
                outline=COLORS["border"],
            )
            content_x = x + 16
            content_y = _draw_card_header(draw, content_x, y + 14, card["name"], theme["accent"])
            data = card["data"]
            if not data.get("success"):
                _draw_error(draw, content_x, content_y, data)
            elif card["id"] == "google":
                _draw_google_card(draw, content_x, content_y, data, theme["accent"])
            elif card["id"] == "xai":
                _draw_xai_card(draw, content_x, content_y, data, theme["accent"])
            elif card["id"] == "openrouter":
                _draw_openrouter_card(draw, content_x, content_y, data, theme["accent"])
            elif card["id"] == "azure":
                _draw_azure_card(draw, content_x, content_y, data, theme["accent"])
            x += CARD_WIDTH + GAP
        y += row_height + GAP

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
