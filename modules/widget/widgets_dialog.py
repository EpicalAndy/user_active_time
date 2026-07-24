"""
Модальный диалог управления мини-виджетами рабочего стола.

Один блок на каждый тип виджета: переключатель «включить/выключить» и его
настройки (рендерятся по схеме `options` из реестра типа). Выключение прячет
виджет, но сохраняет его настройки; настройки применяются сразу.

Несколько экземпляров одного типа диалог не создаёт — это остаётся возможностью
менеджера «под капотом». Стиль — как у прочих диалогов приложения (ttk).
"""

import tkinter as tk
from tkinter import ttk

from config import MAIN_FONT_SIZE
from constants import (
    FONT_FAMILY,
    WIDGETS_DIALOG_CLOSE,
    WIDGETS_DIALOG_TITLE,
)
from modules.ui_utils import center_on_parent
from .mini.registry import options_for, type_menu_items


class WidgetsDialog:
    """Окно вкл/выкл и настройки мини-виджетов (по одному на тип)."""

    def __init__(self, parent: tk.Misc, manager):
        self._parent = parent
        self._manager = manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(WIDGETS_DIALOG_TITLE)
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(parent.winfo_toplevel())
        self.dialog.protocol("WM_DELETE_WINDOW", self._close)

        self._create_widgets()
        center_on_parent(self.dialog, parent)
        self.dialog.focus_set()

    def _create_widgets(self):
        body = tk.Frame(self.dialog)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        for i, (key, label) in enumerate(type_menu_items()):
            if i > 0:
                ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
            self._build_type_block(body, key, label)

        btns = tk.Frame(self.dialog)
        btns.pack(fill=tk.X, padx=12, pady=(0, 10))
        ttk.Button(
            btns, text=WIDGETS_DIALOG_CLOSE, command=self._close,
        ).pack(side=tk.RIGHT)

    def _build_type_block(self, parent: tk.Frame, type_key: str, label: str):
        block = tk.Frame(parent)
        block.pack(fill=tk.X)

        enabled = tk.BooleanVar(value=self._manager.type_enabled(type_key))
        ttk.Checkbutton(
            block, text=label, variable=enabled,
            command=lambda k=type_key, v=enabled: self._manager.set_type_enabled(k, v.get()),
        ).pack(anchor=tk.W)

        opts_frame = tk.Frame(block)
        opts_frame.pack(fill=tk.X, padx=(22, 0))
        current = self._manager.type_opts(type_key)
        for opt in options_for(type_key):
            self._build_option_row(opts_frame, type_key, opt, current)

    def _build_option_row(self, parent: tk.Frame, type_key: str, opt: dict, current: dict):
        row = tk.Frame(parent)
        row.pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            row, text=f"{opt['label']}:", font=(FONT_FAMILY, 9), anchor=tk.W,
        ).pack(side=tk.LEFT)

        var = tk.StringVar(value=str(current.get(opt["key"], opt["default"])))

        def on_change(v=var, k=opt["key"], t=type_key):
            self._manager.update_type_opts(t, {k: v.get()})

        for value, vlabel in opt["choices"]:
            ttk.Radiobutton(
                row, text=vlabel, value=value, variable=var, command=on_change,
            ).pack(side=tk.LEFT, padx=(6, 0))

    def _close(self):
        self.dialog.destroy()

    def wait(self):
        self.dialog.wait_window()
