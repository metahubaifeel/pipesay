"""Clipboard helper — Tk + wl-copy on Wayland for Electron/Cursor."""

import os
import subprocess
import tkinter as tk


def set_clipboard(root: tk.Misc, text: str) -> str:
    """Copy text. On Wayland also runs wl-copy so Ctrl+V works in Cursor/Electron."""
    text = text or ""
    mode = "failed"
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update_idletasks()
        mode = "tk"
    except tk.TclError:
        pass
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
    return mode
