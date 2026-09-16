"""
Вкладка «Метрики»: какие метрики показывать в теле и заголовке виджета,
недельная полоса и её режим, пороги цветовых шкал.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any

import config
from constants import FONT_FAMILY
from texts import (
    METRIC_ACTIVE_TIME,
    METRIC_ACTIVITY_PERCENT_FULL,
    METRIC_FREE_TIME_FULL,
    METRIC_FREE_TIME_PERCENT_FULL,
    METRIC_FULL_DAY_TIME,
    METRIC_FULL_DAY_TIME_PERCENT_FULL,
    METRIC_HIDE_OPTION,
    METRIC_RECOMMENDED_ETA_FULL,
    METRIC_RECOMMENDED_REMAINING_FULL,
    METRIC_RECOMMENDED_REMAINING_PERCENT_FULL,
    METRIC_REMAINING_TIME_FULL,
    METRIC_REMAINING_TIME_PERCENT_FULL,
    METRIC_SESSION_COUNT_FULL,
    METRIC_TIMELINE_FULL,
    METRIC_WEEK_ACTIVITY_FULL,
    METRIC_WORK_DAY_END_FULL,
    WEEK_MODE_CALENDAR_LABEL,
    WEEK_MODE_LABEL,
    WEEK_MODE_ROLLING_LABEL,
)
from modules.week_activity import WEEK_MODE_CALENDAR, WEEK_MODE_ROLLING

# Раскладка чекбоксов «Виджет» — три группы: время | проценты | остальное.
_WIDGET_METRIC_TIME_TOGGLES = [
    ("WIDGET_SHOW_ACTIVE_TIME", METRIC_ACTIVE_TIME),
    ("WIDGET_SHOW_FULL_DAY_TIME", METRIC_FULL_DAY_TIME),
    ("WIDGET_SHOW_RECOMMENDED_REMAINING", METRIC_RECOMMENDED_REMAINING_FULL),
    ("WIDGET_SHOW_REMAINING_TIME", METRIC_REMAINING_TIME_FULL),
    ("WIDGET_SHOW_FREE_TIME", METRIC_FREE_TIME_FULL),
]
_WIDGET_METRIC_PERCENT_TOGGLES = [
    ("WIDGET_SHOW_ACTIVITY_PERCENT", METRIC_ACTIVITY_PERCENT_FULL),
    ("WIDGET_SHOW_FULL_DAY_TIME_PERCENT", METRIC_FULL_DAY_TIME_PERCENT_FULL),
    ("WIDGET_SHOW_RECOMMENDED_REMAINING_PERCENT", METRIC_RECOMMENDED_REMAINING_PERCENT_FULL),
    ("WIDGET_SHOW_REMAINING_TIME_PERCENT", METRIC_REMAINING_TIME_PERCENT_FULL),
    ("WIDGET_SHOW_FREE_TIME_PERCENT", METRIC_FREE_TIME_PERCENT_FULL),
]
_WIDGET_METRIC_OTHER_TOGGLES = [
    ("WIDGET_SHOW_SESSION_COUNT", METRIC_SESSION_COUNT_FULL),
    ("WIDGET_SHOW_WORK_DAY_END", METRIC_WORK_DAY_END_FULL),
    ("WIDGET_SHOW_RECOMMENDED_ETA", METRIC_RECOMMENDED_ETA_FULL),
    ("WIDGET_SHOW_DAY_TIMELINE", METRIC_TIMELINE_FULL),
]
# Недельная полоса — своя группа: у неё, в отличие от прочих метрик, есть
# ещё и режим (какую неделю показывать).
_WIDGET_WEEK_TOGGLE = ("WIDGET_SHOW_WEEK_ACTIVITY", METRIC_WEEK_ACTIVITY_FULL)
_WEEK_MODE_RADIO = [
    (WEEK_MODE_CALENDAR, WEEK_MODE_CALENDAR_LABEL),
    (WEEK_MODE_ROLLING, WEEK_MODE_ROLLING_LABEL),
]

# Полный плоский список — для collect_values, write/apply.
_WIDGET_METRIC_TOGGLES = (
    _WIDGET_METRIC_TIME_TOGGLES
    + _WIDGET_METRIC_PERCENT_TOGGLES
    + _WIDGET_METRIC_OTHER_TOGGLES
    + [_WIDGET_WEEK_TOGGLE]
)

# В заголовке можно выбрать только одну метрику или «Не отображать».
# Пустой attr — значение «ничего не показывать» (все связанные флаги становятся False).
_TITLE_METRIC_RADIO = [
    ("WIDGET_SHOW_TITLE_PERCENT", METRIC_ACTIVITY_PERCENT_FULL),
    ("WIDGET_SHOW_TITLE_REMAINING_TIME", METRIC_REMAINING_TIME_FULL),
    ("WIDGET_SHOW_TITLE_RECOMMENDED_REMAINING", METRIC_RECOMMENDED_REMAINING_FULL),
    ("", METRIC_HIDE_OPTION),
]
_TITLE_METRIC_ATTRS = [attr for attr, _ in _TITLE_METRIC_RADIO if attr]


class MetricsTab:
    """Контролы вкладки «Метрики»; `values()` отдаёт их часть словаря настроек."""

    def __init__(self, parent: tk.Misc):
        self.frame = tk.Frame(parent)
        pad: dict[str, Any] = {"padx": 10, "pady": 4}


        self._metric_vars: dict[str, tk.BooleanVar] = {}

        # --- Виджет ---
        widget_frame = ttk.LabelFrame(self.frame, text="Виджет")
        widget_frame.pack(fill=tk.X, **pad)

        # Время | Проценты — две колонки наверху.
        cols = tk.Frame(widget_frame)
        cols.pack(fill=tk.X, padx=8, pady=(4, 0))
        time_col = tk.Frame(cols)
        time_col.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.N)
        percent_col = tk.Frame(cols)
        percent_col.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.N)

        for attr, label in _WIDGET_METRIC_TIME_TOGGLES:
            var = tk.BooleanVar(value=getattr(config, attr))
            self._metric_vars[attr] = var
            ttk.Checkbutton(time_col, text=label, variable=var).pack(
                anchor=tk.W, pady=2,
            )

        for attr, label in _WIDGET_METRIC_PERCENT_TOGGLES:
            var = tk.BooleanVar(value=getattr(config, attr))
            self._metric_vars[attr] = var
            ttk.Checkbutton(percent_col, text=label, variable=var).pack(
                anchor=tk.W, pady=2,
            )

        # Остальные — внизу на всю ширину.
        for attr, label in _WIDGET_METRIC_OTHER_TOGGLES:
            var = tk.BooleanVar(value=getattr(config, attr))
            self._metric_vars[attr] = var
            ttk.Checkbutton(widget_frame, text=label, variable=var).pack(
                anchor=tk.W, padx=12, pady=2,
            )

        # --- Неделя активности (галочка + режим) ---
        week_frame = ttk.LabelFrame(self.frame, text=METRIC_WEEK_ACTIVITY_FULL)
        week_frame.pack(fill=tk.X, **pad)

        attr, label = _WIDGET_WEEK_TOGGLE
        week_var = tk.BooleanVar(value=getattr(config, attr))
        self._metric_vars[attr] = week_var
        ttk.Checkbutton(week_frame, text="Показывать в виджете", variable=week_var).pack(
            anchor=tk.W, padx=12, pady=2,
        )

        mode_row = tk.Frame(week_frame)
        mode_row.pack(fill=tk.X, padx=12, pady=(0, 4))
        tk.Label(mode_row, text=WEEK_MODE_LABEL, font=(FONT_FAMILY, 9)).pack(side=tk.LEFT)
        self._week_mode_var = tk.StringVar(value=config.WIDGET_WEEK_MODE)
        for value, mode_label in _WEEK_MODE_RADIO:
            ttk.Radiobutton(
                mode_row, text=mode_label, variable=self._week_mode_var, value=value,
            ).pack(side=tk.LEFT, padx=(8, 0))

        # --- Заголовок (одна метрика одновременно) ---
        title_frame = ttk.LabelFrame(self.frame, text="Заголовок")
        title_frame.pack(fill=tk.X, **pad)

        # Начальное значение — первый включённый флаг в конфиге; иначе "ничего"
        initial = ""
        for attr in _TITLE_METRIC_ATTRS:
            if getattr(config, attr):
                initial = attr
                break
        self._title_metric_var = tk.StringVar(value=initial)

        for attr, label in _TITLE_METRIC_RADIO:
            ttk.Radiobutton(
                title_frame, text=label, variable=self._title_metric_var, value=attr,
            ).pack(anchor=tk.W, padx=12, pady=2)

        # --- Пороги ---
        thresholds_frame = ttk.LabelFrame(self.frame, text="Пороги (%)")
        thresholds_frame.pack(fill=tk.X, **pad)

        thr_grid = tk.Frame(thresholds_frame)
        thr_grid.pack(fill=tk.X, padx=8, pady=6)

        # Шапка
        tk.Label(thr_grid, text="Активность", font=(FONT_FAMILY, 9)).grid(
            row=0, column=1, padx=(8, 4), pady=(0, 2),
        )
        tk.Label(thr_grid, text="Рабочее время", font=(FONT_FAMILY, 9)).grid(
            row=0, column=2, padx=(4, 0), pady=(0, 2),
        )

        # Строка «Рекомендуемый»
        tk.Label(thr_grid, text="Рекомендуемый:", font=(FONT_FAMILY, 9)).grid(
            row=1, column=0, sticky=tk.W, pady=2,
        )
        self._recommended_activity_var = tk.IntVar(value=config.RECOMMENDED_ACTIVITY_THRESHOLD)
        ttk.Spinbox(
            thr_grid, from_=0, to=200, width=6,
            textvariable=self._recommended_activity_var, justify=tk.CENTER,
        ).grid(row=1, column=1, padx=(8, 4), pady=2)
        self._recommended_work_var = tk.IntVar(value=config.RECOMMENDED_WORK_TIME_THRESHOLD)
        ttk.Spinbox(
            thr_grid, from_=0, to=200, width=6,
            textvariable=self._recommended_work_var, justify=tk.CENTER,
        ).grid(row=1, column=2, padx=(4, 0), pady=2)

        # Строка «Минимальный»
        tk.Label(thr_grid, text="Минимальный:", font=(FONT_FAMILY, 9)).grid(
            row=2, column=0, sticky=tk.W, pady=2,
        )
        self._min_activity_var = tk.IntVar(value=config.MIN_ACTIVITY_THRESHOLD)
        ttk.Spinbox(
            thr_grid, from_=0, to=200, width=6,
            textvariable=self._min_activity_var, justify=tk.CENTER,
        ).grid(row=2, column=1, padx=(8, 4), pady=2)
        self._min_work_var = tk.IntVar(value=config.MIN_WORK_TIME_THRESHOLD)
        ttk.Spinbox(
            thr_grid, from_=0, to=200, width=6,
            textvariable=self._min_work_var, justify=tk.CENTER,
        ).grid(row=2, column=2, padx=(4, 0), pady=2)

        # Строка «Свободное время» — отдельно под сеткой: у него нет своих
        # рекомендуемого и минимального порогов (они наследуются от активности),
        # поэтому третий столбец дал бы две пустые ячейки. Порог здесь один —
        # граница жёлтой зоны «время заканчивается», в % от бюджета.
        ttk.Separator(thr_grid, orient=tk.HORIZONTAL).grid(
            row=3, column=0, columnspan=3, sticky=tk.EW, pady=(6, 4),
        )
        tk.Label(
            thr_grid, text="Свободное время, предупреждение:", font=(FONT_FAMILY, 9),
        ).grid(row=4, column=0, sticky=tk.W, pady=2)
        self._free_time_warning_var = tk.IntVar(value=config.FREE_TIME_WARNING_PERCENT)
        ttk.Spinbox(
            thr_grid, from_=0, to=100, width=6,
            textvariable=self._free_time_warning_var, justify=tk.CENTER,
        ).grid(row=4, column=1, padx=(8, 4), pady=2)

    def values(self) -> dict:
        body_metrics = {attr: self._metric_vars[attr].get() for attr, _ in _WIDGET_METRIC_TOGGLES}
        selected_title = self._title_metric_var.get()
        title_metrics = {attr: (attr == selected_title) for attr in _TITLE_METRIC_ATTRS}
        return {
            "metrics": {**body_metrics, **title_metrics},
            "week_mode": self._week_mode_var.get(),
            "recommended_activity_threshold": self._recommended_activity_var.get(),
            "min_activity_threshold": self._min_activity_var.get(),
            "recommended_work_time_threshold": self._recommended_work_var.get(),
            "min_work_time_threshold": self._min_work_var.get(),
            "free_time_warning_percent": self._free_time_warning_var.get(),
        }
