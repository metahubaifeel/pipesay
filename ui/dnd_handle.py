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
        text="⋮⋮ 拖/复制",
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
        on_status("已复制 — Cursor 不支持拖入，切过去 Ctrl+V；其他应用可尝试拖放", "info")
        return (COPY, DND_TEXT, text)

    def drag_end(_event):
        on_status("已复制到剪贴板 — 在 Cursor 对话框按 Ctrl+V", "hint")

    handle.drag_source_register(1, DND_TEXT)
    handle.dnd_bind("<<DragInitCmd>>", drag_init)
    handle.dnd_bind("<<DragEndCmd>>", drag_end)

    def show_tip(_event):
        handle.config(fg=fg)

    def hide_tip(_event):
        handle.config(fg=accent)

    tip = "拖到输入框可插入；Cursor 等请用「复制实时」或拖后 Ctrl+V"
    handle.bind("<Enter>", lambda e: (on_status(tip, "hint"), show_tip(e)))
    handle.bind("<Leave>", lambda e: hide_tip(e))

    return handle
