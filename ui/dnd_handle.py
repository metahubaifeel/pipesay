"""Drag-out handle for Coco Dictation Lab."""

import tkinter as tk

try:
    from tkinterdnd2 import COPY, DND_TEXT, REFUSE_DROP

    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    COPY = DND_TEXT = None
    REFUSE_DROP = "refuse_drop"


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
    """Add a drag handle that exports live text to external apps via XDND."""
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

    def drag_init(_event):
        text = (get_text() or "").strip()
        if not text:
            on_empty()
            return REFUSE_DROP
        on_clipboard(text)
        on_status("拖动中…松手到目标输入框；若未插入请 Ctrl+V", "info")
        return (COPY, DND_TEXT, text)

    def drag_end(_event):
        on_status("拖动结束 — 若目标未出现文字，请 Ctrl+V", "hint")

    handle.drag_source_register(1, DND_TEXT)
    handle.dnd_bind("<<DragInitCmd>>", drag_init)
    handle.dnd_bind("<<DragEndCmd>>", drag_end)

    def show_tip(_event):
        handle.config(fg=fg)

    def hide_tip(_event):
        handle.config(fg=accent)

    tip = "拖到输入框松开即可插入；失败时用 Ctrl+V"
    handle.bind("<Enter>", lambda e: (on_status(tip, "hint"), show_tip(e)))
    handle.bind("<Leave>", lambda e: hide_tip(e))

    return handle
