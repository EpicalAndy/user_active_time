"""
Диалог настроек приложения
"""

import os
import re
import tkinter as tk
from tkinter import ttk

import config
from constants import ENCODING, FONT_FAMILY

# Путь к config.py
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.py")

# Дни недели: ключ в WORK_HOURS_BY_DAY → отображаемое название
_DAYS = [
    ("monday", "Пн"),
    ("tuesday", "Вт"),
    ("wednesday", "Ср"),
    ("thursday", "Чт"),
    ("friday", "Пт"),
    ("saturday", "Сб"),
    ("sunday", "Вс"),
]

_WIDGET_METRIC_TOGGLES = [
    ("WIDGET_SHOW_ACTIVE_TIME", "Активное время"),
    ("WIDGET_SHOW_SESSION_COUNT", "Количество сессий"),
    ("WIDGET_SHOW_ACTIVITY_PERCENT", "Активность (%)"),
    ("WIDGET_SHOW_FULL_DAY_TIME", "Рабочее время"),
]

_TITLE_METRIC_TOGGLES = [
    ("WIDGET_SHOW_TITLE_PERCENT", "Активность (%)"),
]

_ALL_METRIC_TOGGLES = _WIDGET_METRIC_TOGGLES + _TITLE_METRIC_TOGGLES


class SettingsDialog:
    """Модальное окно настроек приложения"""

    def __init__(self, parent: tk.Misc):
        self.saved = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Настройки")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self._create_widgets()
        self._center_on_parent(parent)
        self.dialog.focus_set()

    def _center_on_parent(self, parent: tk.Misc):
        self.dialog.update_idletasks()
        dw = self.dialog.winfo_width()
        dh = self.dialog.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2

        # Не даём окну выйти за границы экрана
        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        x = max(0, min(x, sw - dw))
        y = max(0, min(y, sh - dh))
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        pad = {"padx": 10, "pady": 4}

        # --- Вкладки ---
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        tab_general = tk.Frame(notebook)
        tab_metrics = tk.Frame(notebook)
        notebook.add(tab_general, text="Общие")
        notebook.add(tab_metrics, text="Метрики")

        # ===== Вкладка "Общие" =====

        # --- Рабочие часы ---
        hours_frame = ttk.LabelFrame(tab_general, text="Рабочие часы по дням недели")
        hours_frame.pack(fill=tk.X, **pad)

        self._day_vars: dict[str, tk.DoubleVar] = {}
        row = tk.Frame(hours_frame)
        row.pack(fill=tk.X, padx=8, pady=6)

        for key, label in _DAYS:
            col = tk.Frame(row)
            col.pack(side=tk.LEFT, expand=True)
            tk.Label(col, text=label, font=(FONT_FAMILY, 9)).pack()
            var = tk.DoubleVar(value=config.WORK_HOURS_BY_DAY.get(key, config.DEFAULT_WORK_HOURS))
            self._day_vars[key] = var
            ttk.Spinbox(
                col, from_=0, to=24, increment=0.25, width=5,
                textvariable=var, justify=tk.CENTER, format="%.2f",
            ).pack()

        # --- Уведомления ---
        notify_frame = ttk.LabelFrame(tab_general, text="Уведомления")
        notify_frame.pack(fill=tk.X, **pad)

        self._sound_var = tk.BooleanVar(value=config.SOUND_NOTIFICATION)
        ttk.Checkbutton(notify_frame, text="Звук при достижении нормы", variable=self._sound_var).pack(
            anchor=tk.W, padx=12, pady=2,
        )

        # --- Таймеры ---
        timers_frame = ttk.LabelFrame(tab_general, text="Таймеры")
        timers_frame.pack(fill=tk.X, **pad)

        timer_grid = tk.Frame(timers_frame)
        timer_grid.pack(fill=tk.X, padx=8, pady=6)

        tk.Label(timer_grid, text="Таймаут неактивности (сек):", font=(FONT_FAMILY, 9)).grid(
            row=0, column=0, sticky=tk.W, pady=2,
        )
        self._timeout_var = tk.IntVar(value=config.INPUT_ACTIVITY_TIMEOUT)
        ttk.Spinbox(timer_grid, from_=0, to=3600, width=6, textvariable=self._timeout_var).grid(
            row=0, column=1, padx=(8, 0), pady=2,
        )

        tk.Label(timer_grid, text="Предупреждение (сек):", font=(FONT_FAMILY, 9)).grid(
            row=1, column=0, sticky=tk.W, pady=2,
        )
        self._warning_var = tk.IntVar(value=config.COUNTDOWN_WARNING_SECONDS)
        ttk.Spinbox(timer_grid, from_=0, to=300, width=6, textvariable=self._warning_var).grid(
            row=1, column=1, padx=(8, 0), pady=2,
        )

        # ===== Вкладка "Метрики" =====

        self._metric_vars: dict[str, tk.BooleanVar] = {}

        # --- Виджет ---
        widget_frame = ttk.LabelFrame(tab_metrics, text="Виджет")
        widget_frame.pack(fill=tk.X, **pad)

        for attr, label in _WIDGET_METRIC_TOGGLES:
            var = tk.BooleanVar(value=getattr(config, attr))
            self._metric_vars[attr] = var
            ttk.Checkbutton(widget_frame, text=label, variable=var).pack(
                anchor=tk.W, padx=12, pady=2,
            )

        # --- Заголовок ---
        title_frame = ttk.LabelFrame(tab_metrics, text="Заголовок")
        title_frame.pack(fill=tk.X, **pad)

        for attr, label in _TITLE_METRIC_TOGGLES:
            var = tk.BooleanVar(value=getattr(config, attr))
            self._metric_vars[attr] = var
            ttk.Checkbutton(title_frame, text=label, variable=var).pack(
                anchor=tk.W, padx=12, pady=2,
            )

        # --- Кнопки ---
        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Button(btn_frame, text="Отмена", command=self._cancel).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="OK", command=self._save).pack(side=tk.RIGHT, padx=4)

    # --- Сохранение ---

    def _save(self):
        values = self._collect_values()
        self._write_config_file(values)
        self._apply_runtime(values)
        self.saved = True
        self.dialog.destroy()

    def _cancel(self):
        self.dialog.destroy()

    def _collect_values(self) -> dict:
        return {
            "work_hours": {key: self._day_vars[key].get() for key, _ in _DAYS},
            "metrics": {attr: self._metric_vars[attr].get() for attr, _ in _ALL_METRIC_TOGGLES},
            "input_activity_timeout": self._timeout_var.get(),
            "countdown_warning_seconds": self._warning_var.get(),
            "sound_notification": self._sound_var.get(),
        }

    def _write_config_file(self, values: dict):
        with open(_CONFIG_PATH, "r", encoding=ENCODING) as f:
            content = f.read()

        # Таймеры
        content = re.sub(
            r"^INPUT_ACTIVITY_TIMEOUT\s*=\s*.+$",
            f"INPUT_ACTIVITY_TIMEOUT = {values['input_activity_timeout']}",
            content, flags=re.MULTILINE,
        )
        content = re.sub(
            r"^COUNTDOWN_WARNING_SECONDS\s*=\s*.+$",
            f"COUNTDOWN_WARNING_SECONDS = {values['countdown_warning_seconds']}",
            content, flags=re.MULTILINE,
        )
        content = re.sub(
            r"^SOUND_NOTIFICATION\s*=\s*.+$",
            f"SOUND_NOTIFICATION = {values['sound_notification']}",
            content, flags=re.MULTILINE,
        )

        # Метрики
        for attr, val in values["metrics"].items():
            content = re.sub(
                rf"^{attr}\s*=\s*.+$",
                f"{attr} = {val}",
                content, flags=re.MULTILINE,
            )

        # Рабочие часы — заменяем весь блок WORK_HOURS_BY_DAY
        hours = values["work_hours"]
        new_block = "WORK_HOURS_BY_DAY = {\n"
        for key, _ in _DAYS:
            v = hours[key]
            formatted = str(int(v)) if v == int(v) else f"{v:.2f}"
            new_block += f'    "{key}": {formatted},\n'
        new_block += "}"
        content = re.sub(
            r"^WORK_HOURS_BY_DAY\s*=\s*\{[^}]+\}",
            new_block,
            content, flags=re.MULTILINE | re.DOTALL,
        )

        with open(_CONFIG_PATH, "w", encoding=ENCODING) as f:
            f.write(content)

    def _apply_runtime(self, values: dict):
        """Обновляет атрибуты модуля config в памяти"""
        config.SOUND_NOTIFICATION = values["sound_notification"]
        config.INPUT_ACTIVITY_TIMEOUT = values["input_activity_timeout"]
        config.COUNTDOWN_WARNING_SECONDS = values["countdown_warning_seconds"]
        for attr, val in values["metrics"].items():
            setattr(config, attr, val)
        for key, val in values["work_hours"].items():
            config.WORK_HOURS_BY_DAY[key] = val

    def wait(self):
        """Блокирует до закрытия диалога"""
        self.dialog.wait_window()
