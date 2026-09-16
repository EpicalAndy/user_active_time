"""
Вкладка «Инструменты»: настройки инструментов по их схемам `SETTINGS`.

Вкладка не знает ни одного конкретного инструмента: контролы строятся по
схеме из реестра (`tools/registry.py`), а `specs` отдаётся наверх, чтобы
запись в config.py шла по той же схеме.
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

import config
from constants import FONT_FAMILY
from modules.tools.registry import TOOL_CLASSES
from modules.tools.spec import SETTING_BOOL, SETTING_INT, SETTING_TEXT


def has_settings() -> bool:
    """Есть ли хоть у одного инструмента настраиваемые параметры (иначе вкладка не нужна)."""
    return any(getattr(cls, "SETTINGS", None) for cls in TOOL_CLASSES)


class ToolsTab:
    """Контролы вкладки «Инструменты»; `values()` — {АТРИБУТ: значение}."""

    def __init__(self, parent: tk.Misc):
        self.frame = tk.Frame(parent)
        pad: dict[str, Any] = {"padx": 10, "pady": 4}

        self.specs: list[dict] = []
        self._tool_vars: dict[str, tk.Variable] = {}
        for tool_class in TOOL_CLASSES:
            settings = getattr(tool_class, "SETTINGS", None)
            if not settings:
                continue
            frame = ttk.LabelFrame(self.frame, text=tool_class.title)
            frame.pack(fill=tk.X, **pad)
            for spec in settings:
                self._add_tool_setting(frame, spec)

    def _add_tool_setting(self, parent: tk.Misc, spec: dict):
        """Создаёт контрол по схеме настройки инструмента (см. tools/registry.py)."""
        key = spec["key"]
        kind = spec.get("kind", SETTING_BOOL)
        current = getattr(config, key)

        if kind == SETTING_BOOL:
            var: tk.Variable = tk.BooleanVar(value=current)
            ttk.Checkbutton(parent, text=spec["label"], variable=var).pack(
                anchor=tk.W, padx=12, pady=2,
            )
        else:
            row = tk.Frame(parent)
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Label(row, text=spec["label"], font=(FONT_FAMILY, 9)).pack(side=tk.LEFT)

            if kind == SETTING_INT:
                var = tk.IntVar(value=current)
                ttk.Spinbox(
                    row, from_=spec.get("from", 0), to=spec.get("to", 100),
                    increment=spec.get("step", 1), width=6,
                    textvariable=var, justify=tk.CENTER,
                ).pack(side=tk.LEFT, padx=(8, 0))
            else:
                var = tk.StringVar(value=current)
                ttk.Entry(row, textvariable=var, width=spec.get("width", 20)).pack(
                    side=tk.LEFT, padx=(8, 0),
                )

            if spec.get("hint"):
                tk.Label(row, text=spec["hint"], font=(FONT_FAMILY, 8)).pack(
                    side=tk.LEFT, padx=(8, 0),
                )

        self.specs.append(spec)
        self._tool_vars[key] = var

    def values(self) -> dict:
        """Значения настроек инструментов; строки — без крайних пробелов."""
        values = {}
        for spec in self.specs:
            value = self._tool_vars[spec["key"]].get()
            if spec.get("kind", SETTING_BOOL) == SETTING_TEXT:
                value = value.strip()
            values[spec["key"]] = value
        return values

    def validate(self, values: dict) -> bool:
        """Показывает ошибку первой невалидной настройки. True — можно сохранять."""
        for spec in self.specs:
            validate = spec.get("validate")
            if validate is None:
                continue
            error = validate(values[spec["key"]])
            if error is not None:
                messagebox.showerror(*error, parent=self.frame.winfo_toplevel())
                return False
        return True
