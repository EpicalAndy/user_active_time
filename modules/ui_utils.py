"""
Tkinter UI-хелперы.
"""

import tkinter as tk


def center_on_parent(window: tk.Toplevel, parent: tk.Misc) -> None:
    """Центрирует window над parent. Удерживает в пределах экрана."""
    window.update_idletasks()
    dw = window.winfo_width()
    dh = window.winfo_height()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = max(0, min(x, sw - dw))
    y = max(0, min(y, sh - dh))
    window.geometry(f"+{x}+{y}")


def center_on_screen(window: tk.Toplevel) -> None:
    """Центрирует window на экране."""
    window.update_idletasks()
    w = window.winfo_width()
    h = window.winfo_height()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    window.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
