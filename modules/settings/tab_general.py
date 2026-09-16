"""
Вкладка «Общие»: рабочие часы и перерыв, тема, уведомления, трекеры, таймеры.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any

import config
from constants import FONT_FAMILY
from texts import METRIC_BREAK_TIME, SETTINGS_CALENDAR_BUTTON
from modules import theme

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


class GeneralTab:
    """Контролы вкладки «Общие»; `values()` отдаёт их часть словаря настроек."""

    def __init__(self, parent: tk.Misc):
        self.frame = tk.Frame(parent)
        pad: dict[str, Any] = {"padx": 10, "pady": 4}


        # --- Рабочие часы ---
        hours_frame = ttk.LabelFrame(self.frame, text="Рабочие часы")
        hours_frame.pack(fill=tk.X, **pad)

        self._day_vars: dict[str, tk.DoubleVar] = {}
        tk.Label(hours_frame, text="Часы по дням недели:", font=(FONT_FAMILY, 9)).pack(
            anchor=tk.W, padx=8, pady=(6, 0),
        )
        row = tk.Frame(hours_frame)
        row.pack(fill=tk.X, padx=8, pady=(2, 6))

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

        # Перерыв вычитается из нормы активности, но не из рабочих часов —
        # присутствовать нужно всё время, 100% активности считается без перерыва.
        break_row = tk.Frame(hours_frame)
        break_row.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Label(break_row, text=f"{METRIC_BREAK_TIME} (мин):", font=(FONT_FAMILY, 9)).pack(
            side=tk.LEFT,
        )
        self._break_var = tk.IntVar(value=config.BREAK_MINUTES)
        ttk.Spinbox(
            break_row, from_=0, to=480, increment=5, width=6,
            textvariable=self._break_var, justify=tk.CENTER,
        ).pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(
            break_row, text="не входит в норму активности", font=(FONT_FAMILY, 8),
        ).pack(side=tk.LEFT, padx=(8, 0))

        # Привязка лимитов к конкретным датам (исключения из расписания выше).
        ttk.Button(
            hours_frame, text=SETTINGS_CALENDAR_BUTTON,
            command=self._open_schedule_calendar,
        ).pack(anchor=tk.W, padx=8, pady=(0, 8))

        # --- Оформление ---
        appearance_frame = ttk.LabelFrame(self.frame, text="Оформление")
        appearance_frame.pack(fill=tk.X, **pad)

        theme_row = tk.Frame(appearance_frame)
        theme_row.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(theme_row, text="Тема:", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT)
        self._theme_var = tk.StringVar(value=theme.current_theme())
        for name in theme.available_themes():
            ttk.Radiobutton(
                theme_row, text=theme.THEME_LABELS.get(name, name),
                variable=self._theme_var, value=name,
            ).pack(side=tk.LEFT, padx=(12, 0))

        # --- Уведомления ---
        notify_frame = ttk.LabelFrame(self.frame, text="Уведомления")
        notify_frame.pack(fill=tk.X, **pad)

        self._sound_var = tk.BooleanVar(value=config.SOUND_NOTIFICATION)
        ttk.Checkbutton(notify_frame, text="Звук при достижении нормы", variable=self._sound_var).pack(
            anchor=tk.W, padx=12, pady=2,
        )

        self._tick_sound_var = tk.BooleanVar(value=config.COUNTDOWN_TICK_SOUND)
        ttk.Checkbutton(
            notify_frame, text="Сигнал по истечению таймера активности",
            variable=self._tick_sound_var,
        ).pack(anchor=tk.W, padx=12, pady=2)

        self._stop_countdown_var = tk.BooleanVar(value=config.STOP_COUNTDOWN_AT_RECOMMENDED)
        ttk.Checkbutton(
            notify_frame, text="Отключать обратный отсчёт при достижении нормы",
            variable=self._stop_countdown_var,
        ).pack(anchor=tk.W, padx=12, pady=2)

        self._progress_highlight_var = tk.BooleanVar(value=config.WIDGET_PROGRESS_HIGHLIGHT)
        ttk.Checkbutton(
            notify_frame, text="Подсветка виджета о прогрессе",
            variable=self._progress_highlight_var,
        ).pack(anchor=tk.W, padx=12, pady=2)

        # --- Трекеры ---
        trackers_frame = ttk.LabelFrame(self.frame, text="Трекеры")
        trackers_frame.pack(fill=tk.X, **pad)

        self._track_mouse_move_var = tk.BooleanVar(value=config.TRACK_MOUSE_MOVE)
        ttk.Checkbutton(
            trackers_frame, text="Считать движение мыши за активность",
            variable=self._track_mouse_move_var,
        ).pack(anchor=tk.W, padx=12, pady=2)

        # --- Таймеры ---
        timers_frame = ttk.LabelFrame(self.frame, text="Таймеры")
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

    def values(self) -> dict:
        return {
            "work_hours": {key: self._day_vars[key].get() for key, _ in _DAYS},
            "break_minutes": self._break_var.get(),
            "theme": self._theme_var.get(),
            "input_activity_timeout": self._timeout_var.get(),
            "countdown_warning_seconds": self._warning_var.get(),
            "sound_notification": self._sound_var.get(),
            "countdown_tick_sound": self._tick_sound_var.get(),
            "stop_countdown_at_recommended": self._stop_countdown_var.get(),
            "widget_progress_highlight": self._progress_highlight_var.get(),
            "track_mouse_move": self._track_mouse_move_var.get(),
        }

    def _open_schedule_calendar(self):
        # Ленивый импорт: окно нужно только по клику, не при открытии настроек.
        from modules.schedule_calendar import ScheduleCalendar
        ScheduleCalendar(self.frame.winfo_toplevel())
