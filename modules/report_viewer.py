"""
Визуализация отчёта об активности — окно со статистикой и графиком активности/простоя.

Источник — дневной JSON-отчёт; разбор файла и построение интервалов графика
лежат в `report_reader`, здесь только окно и отрисовка на Canvas.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from config import LOG_DIR, MAIN_FONT_SIZE
from constants import FONT_FAMILY
from texts import (
    METRIC_ACTIVE_TIME,
    METRIC_ACTIVITY_NORM,
    METRIC_BREAK_TIME,
    METRIC_FULL_DAY_TIME,
    METRIC_SESSION_COUNT_FULL,
)
from modules import theme
from modules.report_reader import (
    STATE_ACTIVE,
    STATE_INACTIVE,
    STATE_MANUAL,
    parse_report,
    time_to_hours,
)
from modules.ui_utils import center_on_screen


class ReportViewer:
    """Окно визуализации отчёта"""

    def __init__(self, parent: tk.Misc, filepath: str | None = None):
        # filepath задан — открываем конкретный отчёт (например, из тепловой карты);
        # иначе показываем диалог выбора файла.
        if filepath is None:
            filepath = filedialog.askopenfilename(
                parent=parent,
                title="Выберите файл отчёта",
                initialdir=LOG_DIR,
                filetypes=[("JSON-отчёты", "*.json"), ("Все файлы", "*.*")],
            )
            if not filepath:
                return

        data = parse_report(filepath)
        if data is None:
            messagebox.showerror(
                "Ошибка",
                "Выбранный файл не является дневным JSON-отчётом об активности.",
                parent=parent,
            )
            return

        self._show_window(parent, data, os.path.basename(filepath))

    def _show_window(self, parent: tk.Misc, data: dict, filename: str):
        self.win = tk.Toplevel(parent)
        self.win.title(f"Отчёт — {data.get('date', filename)}")
        self.win.resizable(False, False)
        self.win.transient(parent.winfo_toplevel())
        self.win.grab_set()
        self.win.configure(bg=theme.COLOR_DARK_BG)

        # --- Статистика ---
        stats_frame = tk.Frame(self.win, bg=theme.COLOR_DARK_BG, padx=16, pady=12)
        stats_frame.pack(fill=tk.X)

        stats = [
            ("Пользователь", data.get("user", "—")),
            ("Дата", data.get("date", "—")),
            ("Начало и конец рабочего дня", data.get("day_bounds", "—")),
            (METRIC_ACTIVE_TIME, data.get("active_combined", "—")),
            (METRIC_FULL_DAY_TIME, data.get("work_combined", "—")),
            ("Максимальное рабочее время", data.get("max_work_time", "—")),
            (METRIC_BREAK_TIME, data.get("break_time", "—")),
            (METRIC_ACTIVITY_NORM, data.get("activity_norm", "—")),
            (METRIC_SESSION_COUNT_FULL, data.get("session_count", "—")),
        ]

        for label_text, value_text in stats:
            row = tk.Frame(stats_frame, bg=theme.COLOR_DARK_BG)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row, text=f"{label_text}:", bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE), anchor=tk.W,
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text=value_text, bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"), anchor=tk.E,
            ).pack(side=tk.RIGHT)

        # --- Разделитель ---
        tk.Frame(self.win, bg=theme.COLOR_MUTED, height=1).pack(fill=tk.X, padx=16)

        # --- График ---
        chart_label = tk.Label(
            self.win, text="Активность за день", bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
        )
        chart_label.pack(pady=(10, 4))

        self._draw_chart(data)

        # --- Легенда ---
        legend_frame = tk.Frame(self.win, bg=theme.COLOR_DARK_BG)
        legend_frame.pack(pady=(4, 12))

        self._legend_item(legend_frame, theme.COLOR_GREEN, "Активность")
        self._legend_item(legend_frame, theme.COLOR_RED, "Простой")
        self._legend_item(legend_frame, theme.COLOR_BLUE, "Добавленное время")

        # --- Кнопка закрыть ---
        tk.Button(
            self.win, text="Закрыть", command=self.win.destroy,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(pady=(0, 12))

        center_on_screen(self.win)

    def _draw_chart(self, data: dict):
        """Рисует столбчатый график активности на Canvas"""
        events = data.get("events", [])
        intervals = data.get("intervals", [])
        manual_intervals = data.get("manual_intervals", [])

        chart_width = 560
        chart_height = 40
        pad_left = 30
        pad_right = 16
        pad_top = 8
        pad_bottom = 24

        canvas_w = pad_left + chart_width + pad_right
        canvas_h = pad_top + chart_height + pad_bottom

        canvas = tk.Canvas(
            self.win, width=canvas_w, height=canvas_h,
            bg=theme.COLOR_DARK_BG, highlightthickness=0,
        )
        canvas.pack(padx=16, pady=4)

        # Определяем диапазон часов (с учётом ручных интервалов поверх)
        bounds = list(intervals) + [(s, e, STATE_MANUAL) for s, e in manual_intervals]
        if bounds:
            min_hour = max(0, int(min(b[0] for b in bounds)))
            max_hour = min(24, int(max(b[1] for b in bounds)) + 1)
        elif events:
            first_h = int(time_to_hours(events[0][0]))
            last_h = int(time_to_hours(events[-1][0])) + 1
            min_hour = max(0, first_h)
            max_hour = min(24, last_h)
        else:
            min_hour, max_hour = 0, 24

        if max_hour <= min_hour:
            max_hour = min_hour + 1

        hour_span = max_hour - min_hour

        def hour_to_x(h: float) -> float:
            return pad_left + (h - min_hour) / hour_span * chart_width

        # Фон графика
        canvas.create_rectangle(
            pad_left, pad_top,
            pad_left + chart_width, pad_top + chart_height,
            fill=theme.COLOR_LIGHT_GRAY, outline="",
        )

        # Интервалы активности/простоя/ручного времени
        state_colors = {
            STATE_ACTIVE: theme.COLOR_GREEN,
            STATE_INACTIVE: theme.COLOR_RED,
            STATE_MANUAL: theme.COLOR_BLUE,
        }
        for start_h, end_h, state in intervals:
            x1 = hour_to_x(max(start_h, min_hour))
            x2 = hour_to_x(min(end_h, max_hour))
            color = state_colors.get(state, theme.COLOR_RED)
            canvas.create_rectangle(
                x1, pad_top, x2, pad_top + chart_height,
                fill=color, outline="",
            )

        # Ручное время (v2) — отдельным слоем поверх активности/простоя.
        for start_h, end_h in manual_intervals:
            x1 = hour_to_x(max(start_h, min_hour))
            x2 = hour_to_x(min(end_h, max_hour))
            canvas.create_rectangle(
                x1, pad_top, x2, pad_top + chart_height,
                fill=theme.COLOR_BLUE, outline="",
            )

        # Сетка и подписи часов
        for h in range(min_hour, max_hour + 1):
            x = hour_to_x(h)
            # Вертикальная линия сетки
            canvas.create_line(
                x, pad_top, x, pad_top + chart_height,
                fill=theme.COLOR_MUTED, width=1,
            )
            # Подпись часа
            canvas.create_text(
                x, pad_top + chart_height + 4,
                text=str(h), anchor=tk.N,
                fill=theme.COLOR_LIGHT_FG, font=(FONT_FAMILY, 8),
            )

    def _legend_item(self, parent: tk.Frame, color: str, text: str):
        """Добавляет элемент легенды"""
        frame = tk.Frame(parent, bg=theme.COLOR_DARK_BG)
        frame.pack(side=tk.LEFT, padx=12)

        box = tk.Canvas(frame, width=14, height=14, bg=theme.COLOR_DARK_BG, highlightthickness=0)
        box.pack(side=tk.LEFT, padx=(0, 4))
        box.create_rectangle(1, 1, 13, 13, fill=color, outline="")

        tk.Label(
            frame, text=text, bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(side=tk.LEFT)
