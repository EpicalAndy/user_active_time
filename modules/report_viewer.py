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

import config
from config import LOG_DIR, MAIN_FONT_SIZE
from constants import (
    ENCODING,
    FONT_FAMILY,
    METRIC_ACTIVE_TIME,
    METRIC_FULL_DAY_TIME,
    METRIC_SESSION_COUNT_FULL,
)
from modules import activity_intervals, theme
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

    # Парные метрики «время + процент» собираем заранее, чтобы _show_window
    # оставался простым рендером.
    active_combined = _combine_time_percent(active_seconds, max_work_seconds)
    work_combined = _combine_time_percent(total_work_seconds, max_work_seconds)

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

    # Интервалы графика: v2 — из точных sessions/idle с текущим таймаутом;
    # v1 (старые отчёты) — из событий лога, как раньше. Ручное время для v2
    # рисуется отдельным слоем поверх; в v1 оно уже закодировано в intervals.
    try:
        version = int(data.get("version") or 1)
    except (TypeError, ValueError):
        version = 1

    if version >= 2 and date_obj is not None:
        intervals = _v2_intervals(data, date_obj)
        manual_intervals = _manual_hour_intervals(events)
    else:
        intervals = _build_intervals(events)
        manual_intervals = []

    first_login = data.get("first_login")
    last_logout = data.get("last_logout")
    if first_login or last_logout:
        day_bounds = f"{first_login or '—'} — {last_logout or '—'}"
    else:
        day_bounds = "—"

    return {
        "user": data.get("username") or "—",
        "date": date_display,
        "day_bounds": day_bounds,
        "active_combined": active_combined,
        "work_combined": work_combined,
        "max_work_time": _format_dash(max_work_seconds),
        "session_count": str(data.get("session_count") or 0),
        "events": events,
        "intervals": intervals,
        "manual_intervals": manual_intervals,
    }


def _combine_time_percent(seconds, max_work_seconds: int) -> str:
    """Форматирует «Xч Yм Zс (NN.N%)» по секундам и норме.

    Возвращает «—», если seconds None или 0 без нормы; без скобок — если
    нормы нет (поделить не на что).
    """
    if not seconds:
        return "—"
    time_str = format_duration(int(seconds))
    if max_work_seconds <= 0:
        return time_str
    pct = calculate_activity_percent(int(seconds), max_work_seconds / 3600)
    return f"{time_str} ({pct:.1f}%)"


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


_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"


def _parse_iso_intervals(items: list, key_start: str, key_end: str) -> list:
    """Парсит [{key_start, key_end}] (timestamp) в список (datetime, datetime)."""
    out = []
    for it in items or []:
        try:
            out.append((
                datetime.datetime.strptime(it[key_start], _TIMESTAMP_FMT),
                datetime.datetime.strptime(it[key_end], _TIMESTAMP_FMT),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _manual_hour_intervals(events: list) -> list:
    """Интервалы ручного времени (в часах) из пар MANUAL_ADD_START/END."""
    out = []
    start = None
    for ts, etype in sorted(events, key=lambda e: e[0]):
        if etype in _MANUAL_START_EVENTS:
            start = ts
        elif etype in _MANUAL_END_EVENTS and start is not None:
            out.append((_time_to_hours(start), _time_to_hours(ts)))
            start = None
    return out


def _v2_intervals(data: dict, date_obj: datetime.date) -> list:
    """Точные интервалы активности/простоя из сырых sessions/idle (схема v2).

    Таймаут берётся текущий (`config.INPUT_ACTIVITY_TIMEOUT`) — график
    отражает актуальную настройку, как и пересчитанное активное время.
    """
    sessions = _parse_iso_intervals(data.get("sessions"), "start", "end")
    idle = _parse_iso_intervals(data.get("idle"), "from", "to")
    segments = activity_intervals.day_segments(
        sessions, idle, config.INPUT_ACTIVITY_TIMEOUT, date_obj,
    )
    day_start = datetime.datetime.combine(date_obj, datetime.time.min)
    result = []
    for seg_start, seg_end, state in segments:
        start_h = (seg_start - day_start).total_seconds() / 3600
        end_h = (seg_end - day_start).total_seconds() / 3600
        result.append((
            start_h, end_h,
            _STATE_ACTIVE if state == "active" else _STATE_INACTIVE,
        ))
    return result


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
        bounds = list(intervals) + [(s, e, _STATE_MANUAL) for s, e in manual_intervals]
        if bounds:
            min_hour = max(0, int(min(b[0] for b in bounds)))
            max_hour = min(24, int(max(b[1] for b in bounds)) + 1)
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
            fill=theme.COLOR_LIGHT_GRAY, outline="",
        )

        # Интервалы активности/простоя/ручного времени
        state_colors = {
            _STATE_ACTIVE: theme.COLOR_GREEN,
            _STATE_INACTIVE: theme.COLOR_RED,
            _STATE_MANUAL: theme.COLOR_BLUE,
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
