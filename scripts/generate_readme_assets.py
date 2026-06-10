#!/usr/bin/env python3
"""Generate README screenshots and demo GIF (Pillow render, no display needed)."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ASSETS = os.path.join(ROOT, "docs", "assets")

from dictation import (  # noqa: E402
    ACCENT,
    APP_NAME,
    BG,
    BORDER,
    BTN_BG,
    BTN_ON,
    CARD,
    CARD2,
    GREEN,
    MUTED,
    ORANGE,
    PANEL,
    TEXT,
)

W, H = 520, 800
FONT_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
if not os.path.isfile(FONT_CJK):
    FONT_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
FONT_LATIN = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _fonts():
    from PIL import ImageFont

    return {
        "title": ImageFont.truetype(FONT_LATIN, 26),
        "btn": ImageFont.truetype(FONT_CJK, 17),
        "body": ImageFont.truetype(FONT_CJK, 13),
        "body_b": ImageFont.truetype(FONT_CJK, 13),
        "meta": ImageFont.truetype(FONT_CJK, 11),
        "meta_l": ImageFont.truetype(FONT_CJK, 10),
        "live": ImageFont.truetype(FONT_CJK, 15),
        "pill": ImageFont.truetype(FONT_CJK, 11),
    }


def _rect(draw, xy, fill, outline=None, r=8):
    x0, y0, x1, y1 = xy
    if outline:
        draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=1)
    else:
        draw.rounded_rectangle(xy, radius=r, fill=fill)


def _text_center(draw, box, text, font, fill):
    x0, y0, x1, y1 = box
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((x0 + (x1 - x0 - tw) // 2, y0 + (y1 - y0 - th) // 2 - 1), text, font=font, fill=fill)


def render_frame(state: str):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    f = _fonts()
    pad = 20

    # Header
    draw.text((pad, 18), APP_NAME, font=f["title"], fill=TEXT)
    _rect(draw, (W - pad - 52, 20, W - pad, 48), CARD2, outline=BORDER, r=14)
    _text_center(draw, (W - pad - 52, 20, W - pad, 48), "置顶", f["pill"], MUTED)

    y = 72
    _rect(draw, (pad, y, W - pad, y + 200), PANEL, outline=BORDER)

    # Record button
    btn_color = BTN_ON if state == "live" else BTN_BG
    btn_text = "停止录音" if state == "live" else "开始录音"
    _rect(draw, (pad + 16, y + 16, W - pad - 16, y + 68), btn_color, r=10)
    _text_center(draw, (pad + 16, y + 16, W - pad - 16, y + 68), btn_text, f["btn"], TEXT)

    if state == "idle":
        status, status_fg = "就绪 — 空格键可开始/停止", MUTED
    elif state == "live":
        status, status_fg = "正在听写…", ORANGE
    else:
        status, status_fg = "完成 — 32 字 · 已复制", GREEN
    draw.text((pad + 16, y + 78), status, font=f["meta"], fill=status_fg)

    # Level meter
    my = y + 108
    draw.text((pad + 16, my), "输入", font=f["meta_l"], fill=MUTED)
    bar_x0, bar_x1 = pad + 56, W - pad - 56
    _rect(draw, (bar_x0, my + 2, bar_x1, my + 18), CARD, r=6)
    pct = 0.48 if state == "live" else (0.12 if state == "idle" else 0.05)
    fill_w = int((bar_x1 - bar_x0) * pct)
    if fill_w > 4:
        _rect(draw, (bar_x0, my + 2, bar_x0 + fill_w, my + 18), ACCENT, r=6)
    draw.text((bar_x1 + 8, my), f"{int(pct * 100)}%", font=f["meta_l"], fill=MUTED)

    y += 210
    draw.text((pad, y), "✓ 识别完自动复制", font=f["body"], fill=MUTED)
    draw.text((W - pad - 120, y), "Soniox 云端", font=f["meta"], fill=MUTED)

    y += 32
    _rect(draw, (pad, y, W - pad, y + 44), PANEL, outline=BORDER)
    draw.text((pad + 12, y + 12), "引擎", font=f["meta"], fill=MUTED)
    _rect(draw, (pad + 56, y + 8, pad + 150, y + 36), ACCENT, r=14)
    _text_center(draw, (pad + 56, y + 8, pad + 150, y + 36), "Soniox 云端", f["pill"], TEXT)
    _rect(draw, (pad + 158, y + 8, pad + 268, y + 36), CARD2, outline=BORDER, r=14)
    _text_center(draw, (pad + 158, y + 8, pad + 268, y + 36), "本地 Whisper", f["pill"], MUTED)

    y += 54
    draw.text((pad, y), "麦克风 · PipeWire · 48 kHz", font=f["meta"], fill="#52525b")

    live_text = "在 Linux Wayland 桌面上做实时听写"
    final_text = "在 Linux Wayland 桌面上做实时听写，停录后自动复制到剪贴板。"

    if state == "live":
        y += 28
        _rect(draw, (pad, y, W - pad, y + 130), PANEL, outline=ACCENT)
        draw.text((pad + 12, y + 10), "实时转写", font=f["body_b"], fill=ACCENT)
        _rect(draw, (W - pad - 88, y + 6, W - pad - 12, y + 30), CARD2, outline=BORDER, r=10)
        _text_center(draw, (W - pad - 88, y + 6, W - pad - 12, y + 30), "复制实时", f["pill"], TEXT)
        _rect(draw, (pad + 8, y + 38, W - pad - 8, y + 118), CARD, r=6)
        draw.text((pad + 20, y + 52), live_text + " …", font=f["live"], fill=TEXT)
        y += 140

    y += 16
    draw.text((pad, y), "识别结果", font=f["body_b"], fill=MUTED)
    if state == "done":
        y += 28
        _rect(draw, (pad, y, W - pad, y + 100), PANEL, outline=BORDER)
        _rect(draw, (pad + 8, y + 8, W - pad - 8, y + 92), CARD, r=6)
        draw.text((pad + 20, y + 22), final_text, font=f["live"], fill=TEXT)
    else:
        y += 28
        _rect(draw, (pad, y, W - pad, y + 72), PANEL, outline=BORDER)
        _rect(draw, (pad + 8, y + 8, W - pad - 8, y + 64), CARD, r=6)

    # Toolbar hint
    draw.text((pad, H - 36), "复制全部 · 清空 · 保存", font=f["meta"], fill="#3f3f46")

    return img


def main():
    try:
        from PIL import Image
    except ImportError:
        print("Install Pillow: .venv/bin/pip install pillow")
        return 1

    os.makedirs(ASSETS, exist_ok=True)
    mapping = {
        "demo-idle.png": "idle",
        "demo-live.png": "live",
        "demo-done.png": "done",
    }
    frames = []
    for name, state in mapping.items():
        img = render_frame(state)
        path = os.path.join(ASSETS, name)
        img.save(path, optimize=True)
        frames.append(img)
        print(f"  {name}: {os.path.getsize(path) // 1024} KiB")

    gif_path = os.path.join(ASSETS, "demo.gif")
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=2000,
        loop=0,
        optimize=True,
    )
    print(f"  demo.gif: {os.path.getsize(gif_path) // 1024} KiB")
    print("Wrote:", ASSETS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
