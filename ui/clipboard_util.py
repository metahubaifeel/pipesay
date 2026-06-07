"""Wayland-friendly clipboard helper for Coco Dictation Lab."""

import os
import subprocess
import tkinter as tk


def set_clipboard(root: tk.Misc, text: str) -> str:
    """Copy text; on Wayland prefer wl-copy so Ctrl+V works in Cursor/Electron."""
    text = text or ""
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        try:
            subprocess.run(
                ["wl-copy"],
                input=text.encode("utf-8"),
                check=True,
                timeout=2,
            )
            return "wayland"
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update_idletasks()
        return "tk"
    except tk.TclError:
        return "failed"
