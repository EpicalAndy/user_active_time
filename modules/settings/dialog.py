"""
Диалог настроек приложения: окно, вкладки, кнопки, сбор значений.

Содержимое вкладок — в `tab_general` / `tab_metrics` / `tab_tools`, каждая
отдаёт свою часть плоского словаря настроек через `values()`. Запись
собранного в config.py и применение на лету — в `writer`.
"""

import tkinter as tk
from tkinter import ttk

from modules.ui_utils import center_on_parent
from .tab_general import GeneralTab
from .tab_metrics import MetricsTab
from .tab_tools import ToolsTab, has_settings
from .writer import apply_runtime, write_config_file


class SettingsDialog:
    """Модальное окно настроек приложения"""

    def __init__(self, parent: tk.Misc):
        self.saved = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Настройки")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(parent.winfo_toplevel())
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self._create_widgets()
        center_on_parent(self.dialog, parent)
        self.dialog.focus_set()

    def _create_widgets(self):
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        self._general = GeneralTab(notebook)
        self._metrics = MetricsTab(notebook)
        self._tools = ToolsTab(notebook)
        notebook.add(self._general.frame, text="Общие")
        notebook.add(self._metrics.frame, text="Метрики")
        # Вкладка инструментов появляется, только если хоть у одного инструмента
        # есть настраиваемые параметры.
        if has_settings():
            notebook.add(self._tools.frame, text="Инструменты")

        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Button(btn_frame, text="Отмена", command=self._cancel).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="OK", command=self._save).pack(side=tk.RIGHT, padx=4)

    # --- Сохранение ---

    def _save(self):
        # Настройки инструментов проверяем до записи: например, конфиг с
        # неразбираемой комбинацией оставил бы блокировку ввода без разблокировки.
        tool_values = self._tools.values()
        if not self._tools.validate(tool_values):
            return

        values = self._collect_values()
        write_config_file(values, self._tools.specs)
        apply_runtime(values)
        self.saved = True
        self.dialog.destroy()

    def _cancel(self):
        self.dialog.destroy()

    def _collect_values(self) -> dict:
        """Плоский словарь настроек — формат см. в шапке `writer`."""
        return {
            **self._general.values(),
            **self._metrics.values(),
            "tools": self._tools.values(),
        }

    def wait(self):
        """Блокирует до закрытия диалога"""
        self.dialog.wait_window()
