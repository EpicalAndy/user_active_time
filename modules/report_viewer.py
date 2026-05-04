"""
Визуализация отчёта об активности — окно со статистикой и графиком активности/простоя.
Источник — дневной JSON-отчёт.
"""

import datetime
import json
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

from config import LOG_DIR, MAIN_FONT_SIZE
from constants import (
    COLOR_BLUE,
    COLOR_DARK_BG,
    COLOR_GREEN,
    COLOR_LIGHT_FG,
    COLOR_LIGHT_GRAY,
    COLOR_MUTED,
    COLOR_RED,
    ENCODING,
    FONT_FAMILY,
    METRIC_ACTIVE_TIME,
    METRIC_ACTIVITY_PERCENT,
    METRIC_FIRST_LOGIN,
    METRIC_LAST_LOGOUT,
    METRIC_SESSION_COUNT,
)
from modules.ui_utils import center_on_screen
from utility import calculate_activity_percent, format_duration

# Типы событий → активность
_ACTIVE_EVENTS = {"LOGON", "UNLOCK", "INPUT_ACTIVE", "MONITOR_START"}
_INACTIVE_EVENTS = {"LOGOFF", "LOCK", "INPUT_INACTIVE", "MONITOR_STOP"}
_MANUAL_START_EVENTS = {"MANUAL_ADD_START"}
_MANUAL_END_EVENTS = {"MANUAL_ADD_END"}

# Состояния интервалов графика
_STATE_ACTIVE = "active"
_STATE_INACTIVE = "inactive"
_STATE_MANUAL = "manual"

_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*\S+\s*\|\s*(\S+)"
)


def _format_dash(seconds) -> str:
    """Форматирует секунды; «—» если None или ноль для опциональных метрик."""
    if seconds is None:
        return "—"
    return format_duration(int(seconds))


def _parse_report(filepath: str) -> dict | None:
    """Загружает дневной JSON-отчёт. Возвращает dict с готовыми к показу значениями
    либо None, если файл нельзя интерпретировать.
    """
    try:
        with open(filepath, "r", encoding=ENCODING) as f:
            data = json.load(f)
    except (IOError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "active_seconds" not in data:
        return None

    # Дата: в файле YYYY-MM-DD, отображаем dd.mm.yyyy
    date_iso = data.get("date") or ""
    try:
        date_obj = datetime.date.fromisoformat(date_iso) if date_iso else None
        date_display = date_obj.strftime("%d.%m.%Y") if date_obj else "—"
    except ValueError:
        date_display = date_iso or "—"

    active_seconds = int(data.get("active_seconds") or 0)
    max_work_seconds = int(data.get("max_work_seconds") or 0)
    total_work_seconds = data.get("total_work_seconds")

    # Процент считаем здесь — в файле его нет (производное значение).
    if max_work_seconds > 0:
        pct = calculate_activity_percent(active_seconds, max_work_seconds / 3600)
        activity_percent = f"{pct:.1f}%"
    else:
        activity_percent = "—"

    # Парсим строки лога (формат строки не менялся при переходе на JSON).
    events = []
    for line in data.get("log") or []:
        m = _LOG_LINE_RE.match(str(line).strip())
        if not m:
            continue
        try:
            ts = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        events.append((ts, m.group(2)))

    return {
        "user": data.get("username") or "—",
        "date": date_display,
        "first_login": data.get("first_login") or "—",
        "last_logout": data.get("last_logout") or "—",
        "active_time": _format_dash(active_seconds),
        "max_work_time": _format_dash(max_work_seconds),
        "total_work_time": _format_dash(total_work_seconds),
        "session_count": str(data.get("session_count") or 0),
        "activity_percent": activity_percent,
        "events": events,
    }


def _build_intervals(events: list[tuple[datetime.datetime, str]]) -> list[tuple[float, float, str]]:
    """
    Строит интервалы активности/простоя/ручного времени из событий.
    Возвращает список (start_hour, end_hour, state),
    где state ∈ {"active", "inactive", "manual"}.
    """
    if not events:
        return []

    # Сортируем по времени на случай, если ручные записи были добавлены задним числом
    events = sorted(events, key=lambda e: e[0])

    intervals = []
    is_active = True  # После первого события (MONITOR_START/LOGON) считаем активным
    is_manual = False  # Ручной интервал перекрывает визуальное состояние
    prev_hour = _time_to_hours(events[0][0])

    for ts, event_type in events:
        hour = _time_to_hours(ts)

        if hour > prev_hour:
            if is_manual:
                state = _STATE_MANUAL
            else:
                state = _STATE_ACTIVE if is_active else _STATE_INACTIVE
            intervals.append((prev_hour, hour, state))

        if event_type in _ACTIVE_EVENTS:
            is_active = True
        elif event_type in _INACTIVE_EVENTS:
            is_active = False
        elif event_type in _MANUAL_START_EVENTS:
            is_manual = True
        elif event_type in _MANUAL_END_EVENTS:
            is_manual = False

        prev_hour = hour

    # Последний интервал до последнего события (уже добавлен)
    return intervals


def _time_to_hours(dt: datetime.datetime) -> float:
    """Переводит время в дробные часы (0.0 — 24.0)"""
    return dt.hour + dt.minute / 60 + dt.second / 3600


class ReportViewer:
    """Окно визуализации отчёта"""

    def __init__(self, parent: tk.Misc):
        filepath = filedialog.askopenfilename(
            parent=parent,
            title="Выберите файл отчёта",
            initialdir=LOG_DIR,
            filetypes=[("JSON-отчёты", "*.json"), ("Все файлы", "*.*")],
        )

        if not filepath:
            return

        data = _parse_report(filepath)
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
        self.win.configure(bg=COLOR_DARK_BG)

        # --- Статистика ---
        stats_frame = tk.Frame(self.win, bg=COLOR_DARK_BG, padx=16, pady=12)
        stats_frame.pack(fill=tk.X)

        stats = [
            ("Пользователь", data.get("user", "—")),
            ("Дата", data.get("date", "—")),
            (METRIC_FIRST_LOGIN, data.get("first_login", "—")),
            (METRIC_LAST_LOGOUT, data.get("last_logout", "—")),
            (METRIC_ACTIVE_TIME, data.get("active_time", "—")),
            ("Рабочее время", data.get("total_work_time", "—")),
            ("Макс. рабочее время", data.get("max_work_time", "—")),
            (METRIC_SESSION_COUNT, data.get("session_count", "—")),
            (METRIC_ACTIVITY_PERCENT, data.get("activity_percent", "—")),
        ]

        for label_text, value_text in stats:
            row = tk.Frame(stats_frame, bg=COLOR_DARK_BG)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row, text=f"{label_text}:", bg=COLOR_DARK_BG, fg=COLOR_MUTED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE), anchor=tk.W,
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text=value_text, bg=COLOR_DARK_BG, fg=COLOR_LIGHT_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"), anchor=tk.E,
            ).pack(side=tk.RIGHT)

        # --- Разделитель ---
        tk.Frame(self.win, bg=COLOR_MUTED, height=1).pack(fill=tk.X, padx=16)

        # --- График ---
        chart_label = tk.Label(
            self.win, text="Активность за день", bg=COLOR_DARK_BG, fg=COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
        )
        chart_label.pack(pady=(10, 4))

        self._draw_chart(data)

        # --- Легенда ---
        legend_frame = tk.Frame(self.win, bg=COLOR_DARK_BG)
        legend_frame.pack(pady=(4, 12))

        self._legend_item(legend_frame, COLOR_GREEN, "Активность")
        self._legend_item(legend_frame, COLOR_RED, "Простой")
        self._legend_item(legend_frame, COLOR_BLUE, "Добавленное время")

        # --- Кнопка закрыть ---
        tk.Button(
            self.win, text="Закрыть", command=self.win.destroy,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(pady=(0, 12))

        center_on_screen(self.win)

    def _draw_chart(self, data: dict):
        """Рисует столбчатый график активности на Canvas"""
        events = data.get("events", [])
        intervals = _build_intervals(events)

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
            bg=COLOR_DARK_BG, highlightthickness=0,
        )
        canvas.pack(padx=16, pady=4)

        # Определяем диапазон часов
        if intervals:
            min_hour = max(0, int(intervals[0][0]))
            max_hour = min(24, int(intervals[-1][1]) + 1)
        elif events:
            first_h = int(_time_to_hours(events[0][0]))
            last_h = int(_time_to_hours(events[-1][0])) + 1
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
            fill=COLOR_LIGHT_GRAY, outline="",
        )

        # Интервалы активности/простоя/ручного времени
        state_colors = {
            _STATE_ACTIVE: COLOR_GREEN,
            _STATE_INACTIVE: COLOR_RED,
            _STATE_MANUAL: COLOR_BLUE,
        }
        for start_h, end_h, state in intervals:
            x1 = hour_to_x(max(start_h, min_hour))
            x2 = hour_to_x(min(end_h, max_hour))
            color = state_colors.get(state, COLOR_RED)
            canvas.create_rectangle(
                x1, pad_top, x2, pad_top + chart_height,
                fill=color, outline="",
            )

        # Сетка и подписи часов
        for h in range(min_hour, max_hour + 1):
            x = hour_to_x(h)
            # Вертикальная линия сетки
            canvas.create_line(
                x, pad_top, x, pad_top + chart_height,
                fill=COLOR_MUTED, width=1,
            )
            # Подпись часа
            canvas.create_text(
                x, pad_top + chart_height + 4,
                text=str(h), anchor=tk.N,
                fill=COLOR_LIGHT_FG, font=(FONT_FAMILY, 8),
            )

    def _legend_item(self, parent: tk.Frame, color: str, text: str):
        """Добавляет элемент легенды"""
        frame = tk.Frame(parent, bg=COLOR_DARK_BG)
        frame.pack(side=tk.LEFT, padx=12)

        box = tk.Canvas(frame, width=14, height=14, bg=COLOR_DARK_BG, highlightthickness=0)
        box.pack(side=tk.LEFT, padx=(0, 4))
        box.create_rectangle(1, 1, 13, 13, fill=color, outline="")

        tk.Label(
            frame, text=text, bg=COLOR_DARK_BG, fg=COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        ).pack(side=tk.LEFT)
