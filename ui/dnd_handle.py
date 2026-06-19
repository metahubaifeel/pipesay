"""Drag-out handle for PipeSay Lab."""

import sys
import tkinter as tk

try:
    from tkinterdnd2 import COPY, DND_TEXT, REFUSE_DROP

    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    COPY = DND_TEXT = None
    REFUSE_DROP = "refuse_drop"

_DRAG_THRESHOLD = 6

# UTF-8 MIME for CJK. Do NOT also offer bare "text/plain" or multiple pair entries —
# Cursor/Electron may prepend "text/plain" or insert Tcl-style "text/plain {…}".
_LINUX_UTF8_TYPE = "text/plain;charset=utf-8"


def _drag_payload(text: str):
    """Single (type, data) pair — avoids multi-format garbage in Cursor."""
    if sys.platform == "win32":
        return (COPY, DND_TEXT, text)
    # len==2 form with ONE pair; tkdnd expands this type once.
    return (COPY, (_LINUX_UTF8_TYPE, text))


def attach_drag_handle(
    parent,
    *,
    get_text,
    on_status,
    on_empty,
    on_clipboard,
    bg,
    fg,
    muted,
    accent,
):
    """Drag handle: drag to Cursor / Discord; click without move = copy."""
    if not DND_AVAILABLE:
        label = tk.Label(
            parent,
            text="拖放不可用",
            font=("Segoe UI", 9),
            bg=bg,
            fg=muted,
        )
        label.pack(side="right", padx=(6, 0))
        return label

    handle = tk.Label(
        parent,
        text="⋮⋮ 拖动",
        font=("Segoe UI", 10, "bold"),
        bg=bg,
        fg=accent,
        cursor="hand2",
        padx=6,
        pady=2,
    )
    handle.pack(side="right", padx=(6, 0))

    pointer = {"x": 0, "y": 0, "moved": False, "dragging": False}

    def copy_only():
        text = (get_text() or "").strip()
        if not text:
            on_empty()
            return
        on_clipboard(text)
        on_status("已复制 — 可 Ctrl+V 粘贴", "ok")

    def on_press(event):
        pointer.update(x=event.x, y=event.y, moved=False, dragging=False)

    def on_motion(event):
        if pointer["moved"]:
            return
        if (
            abs(event.x - pointer["x"]) > _DRAG_THRESHOLD
            or abs(event.y - pointer["y"]) > _DRAG_THRESHOLD
        ):
            pointer["moved"] = True

    def on_release(_event):
        if not pointer["moved"] and not pointer["dragging"]:
            copy_only()

    def drag_init(_event):
        text = (get_text() or "").strip()
        if not text:
            on_empty()
            return REFUSE_DROP
        pointer["dragging"] = True
        pointer["moved"] = True
        on_clipboard(text)
        on_status("拖动中…松手到 Cursor / 输入框", "info")
        return _drag_payload(text)

    def drag_end(_event):
        pointer["dragging"] = False
        action = getattr(_event, "action", None)
        if action and action not in ("", "refuse_drop", REFUSE_DROP):
            on_status("已拖入目标", "ok")
        else:
            on_status("未拖入？已复制 — 可 Ctrl+V", "hint")

    handle.bind("<ButtonPress-1>", on_press)
    handle.bind("<B1-Motion>", on_motion)
    handle.bind("<ButtonRelease-1>", on_release)
    # Register DND_TEXT so X11 drag works; payload uses UTF-8 MIME only.
    if sys.platform == "win32":
        handle.drag_source_register(1, DND_TEXT)
    else:
        handle.drag_source_register(1, DND_TEXT, _LINUX_UTF8_TYPE)
    handle.dnd_bind("<<DragInitCmd>>", drag_init)
    handle.dnd_bind("<<DragEndCmd>>", drag_end)

    def show_tip(_event):
        handle.config(fg=fg)

    def hide_tip(_event):
        handle.config(fg=accent)

    tip = "拖到 Cursor / 聊天框；点一下不移动 = 复制"
    handle.bind("<Enter>", lambda e: (on_status(tip, "hint"), show_tip(e)))
    handle.bind("<Leave>", lambda e: hide_tip(e))

    return handle
