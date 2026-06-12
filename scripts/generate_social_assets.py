#!/usr/bin/env python3
"""Generate social-media images (小红书 / X / 即刻)."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ASSETS = os.path.join(ROOT, "docs", "assets", "social")

from scripts.generate_readme_assets import (  # noqa: E402
    ACCENT,
    APP_NAME,
    BG,
    BORDER,
    BTN_BG,
    CARD,
    CARD2,
    GREEN,
    MUTED,
    ORANGE,
    PANEL,
    TEXT,
    FONT_CJK,
    FONT_LATIN,
    _rect,
    render_frame,
)

XHS_W, XHS_H = 1080, 1440
X_W, X_H = 1200, 675


def _fonts():
    from PIL import ImageFont

    return {
        "hero": ImageFont.truetype(FONT_CJK, 72),
        "hero_en": ImageFont.truetype(FONT_LATIN, 80),
        "h1": ImageFont.truetype(FONT_CJK, 52),
        "h2": ImageFont.truetype(FONT_CJK, 36),
        "body": ImageFont.truetype(FONT_CJK, 30),
        "body_s": ImageFont.truetype(FONT_CJK, 26),
        "pill": ImageFont.truetype(FONT_CJK, 22),
        "url": ImageFont.truetype(FONT_LATIN, 24),
        "step": ImageFont.truetype(FONT_CJK, 34),
    }


def _slide_base():
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (XHS_W, XHS_H), BG)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((36, 36, XHS_W - 36, XHS_H - 36), radius=28, fill=PANEL, outline=BORDER)
    return img, draw


def render_xhs_cover():
    img, draw = _slide_base()
    f = _fonts()
    draw.text((72, 100), APP_NAME, font=f["hero_en"], fill=TEXT)
    draw.text((72, 200), "Linux 说话变文字", font=f["hero"], fill=ACCENT)
    draw.text((72, 300), "开源桌面听写小工具", font=f["h2"], fill=TEXT)
    draw.text((72, 370), "Web Coding · 上课 · 看课记笔记", font=f["body_s"], fill=MUTED)

    for i, label in enumerate(["实时出字", "停录复制", "MIT 开源"]):
        x = 72 + i * 310
        _rect(draw, (x, 400, x + 280, 470), CARD2, outline=ACCENT, r=20)
        bb = draw.textbbox((0, 0), label, font=f["pill"])
        tw = bb[2] - bb[0]
        draw.text((x + (280 - tw) // 2, 418), label, font=f["pill"], fill=TEXT)

    preview = render_frame("live")
    from PIL import Image

    preview.thumbnail((780, 900), Image.LANCZOS)
    px = (XHS_W - preview.width) // 2
    py = 520
    draw.rounded_rectangle(
        (px - 14, py - 14, px + preview.width + 14, py + preview.height + 14),
        radius=24,
        outline=ACCENT,
    )
    img.paste(preview, (px, py))
    draw.text((72, XHS_H - 120), "左滑看用法 →", font=f["body_s"], fill=MUTED)
    return img


def render_xhs_scenarios():
    img, draw = _slide_base()
    f = _fonts()
    draw.text((72, 80), "什么时候用？", font=f["h1"], fill=TEXT)
    draw.text((72, 155), "三个我每天都在用的场景", font=f["body_s"], fill=MUTED)
    scenarios = [
        ("💻", "Web Coding", "Cursor 旁挂小窗，边说边出字\n停录 Ctrl+V 贴进编辑器"),
        ("🎓", "上课 / 听讲座", "网课、组会、分享会\n口述笔记实时变文字"),
        ("📺", "看课 / 录屏记笔记", "边看教程边讲想法\n录屏做分享时口述旁白也行"),
    ]
    y = 220
    box_h = 340
    for icon, title, sub in scenarios:
        _rect(draw, (72, y, XHS_W - 72, y + box_h), CARD2, outline=BORDER, r=20)
        draw.text((100, y + 28), icon, font=f["h1"], fill=TEXT)
        draw.text((180, y + 24), title, font=f["step"], fill=ACCENT)
        for i, line in enumerate(sub.split("\n")):
            draw.text((100, y + 100 + i * 48), line, font=f["body_s"], fill=TEXT)
        y += box_h + 28
    draw.text((72, XHS_H - 100), "Linux · Wayland · 空格开始/停止", font=f["body_s"], fill=MUTED)
    return img


def render_xhs_screenshot(state: str, caption: str):
    from PIL import Image

    img, draw = _slide_base()
    f = _fonts()
    draw.text((72, 80), caption, font=f["h1"], fill=ACCENT)
    preview = render_frame(state)
    preview.thumbnail((920, 1100), Image.LANCZOS)
    px = (XHS_W - preview.width) // 2
    py = 200
    draw.rounded_rectangle(
        (px - 12, py - 12, px + preview.width + 12, py + preview.height + 12),
        radius=20,
        outline=BORDER,
    )
    img.paste(preview, (px, py))
    return img


def render_xhs_cta():
    img, draw = _slide_base()
    f = _fonts()
    draw.text((72, 100), "GitHub 开源", font=f["h1"], fill=TEXT)
    draw.text((72, 190), "github.com/metahubaifeel/pipesay", font=f["url"], fill=ACCENT)

    bullets = [
        "✅ Linux + PipeWire + Wayland",
        "✅ 空格开始/停止 · 小窗常驻",
        "✅ Lab 分支有拖放实验",
        "⚠️ 需要 Soniox Key（按量计费）",
        "⚠️ Linux only · 按现状提供",
    ]
    y = 320
    for line in bullets:
        color = MUTED if line.startswith("⚠️") else TEXT
        draw.text((72, y), line, font=f["body"], fill=color)
        y += 70

    _rect(draw, (72, XHS_H - 200, XHS_W - 72, XHS_H - 110), BTN_BG, r=20)
    draw.text((120, XHS_H - 175), "Star · Issue · 欢迎 Linux 用户试用", font=f["body_s"], fill=GREEN)
    return img


def render_x_card():
    """1200×675 for X / Twitter post attachment."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (X_W, X_H), BG)
    draw = ImageDraw.Draw(img)
    f = _fonts()
    title_f = ImageFont.truetype(FONT_LATIN, 88)
    draw.rounded_rectangle((32, 32, X_W - 32, X_H - 32), radius=24, fill=PANEL, outline=BORDER)
    draw.text((56, 56), APP_NAME, font=title_f, fill=TEXT)
    draw.text((56, 170), "Live dictation for Linux", font=f["h2"], fill=ACCENT)
    draw.text((56, 230), "Speak → real-time text → auto-copy on stop", font=f["body_s"], fill=TEXT)
    draw.text((56, 290), "PipeWire · Wayland · MIT OSS", font=f["pill"], fill=MUTED)

    preview = render_frame("live")
    preview.thumbnail((280, 420), Image.LANCZOS)
    px = X_W - preview.width - 56
    py = (X_H - preview.height) // 2
    draw.rounded_rectangle(
        (px - 10, py - 10, px + preview.width + 10, py + preview.height + 10),
        radius=16,
        outline=ACCENT,
    )
    img.paste(preview, (px, py))
    draw.text((56, X_H - 72), "github.com/metahubaifeel/pipesay", font=f["url"], fill=MUTED)
    return img


def main():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("Install Pillow: .venv/bin/pip install pillow")
        return 1

    os.makedirs(ASSETS, exist_ok=True)
    items = [
        ("xhs-01-cover.png", render_xhs_cover()),
        ("xhs-02-scenarios.png", render_xhs_scenarios()),
        ("xhs-03-live.png", render_xhs_screenshot("live", "实时转写")),
        ("xhs-04-done.png", render_xhs_screenshot("done", "停录 · 自动复制")),
        ("xhs-05-cta.png", render_xhs_cta()),
        ("x-card.png", render_x_card()),
    ]
    for name, img in items:
        path = os.path.join(ASSETS, name)
        img.save(path, optimize=True)
        print(f"  {name}: {os.path.getsize(path) // 1024} KiB")
    print("Wrote:", ASSETS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
