"""
Чтение дневного JSON-отчёта для окна просмотра.

Отдаёт готовые к показу значения (строки метрик) и размеченные интервалы для
графика активности/простоя/ручного времени. Без tkinter: окно
(`report_viewer.ReportViewer`) только рендерит то, что вернул `parse_report`.

Две схемы отчёта:
- v2 — интервалы графика считаются из сырых `sessions`/`idle` с ТЕКУЩИМ
  таймаутом неактивности (`activity_intervals.day_segments`), ручное время
  рисуется отдельным слоем поверх;
- v1 (старые отчёты) — из событий лога (`build_intervals`), ручное время уже
  закодировано в интервалах.
"""

import datetime
import json
import re

import config
from constants import ENCODING
from modules import activity_intervals
from utility import (
    calculate_activity_percent,
    format_duration,
    format_percent,
    get_input_timeout,
)

# Типы событий → активность
_ACTIVE_EVENTS = {"LOGON", "UNLOCK", "INPUT_ACTIVE", "MONITOR_START"}
_INACTIVE_EVENTS = {"LOGOFF", "LOCK", "INPUT_INACTIVE", "MONITOR_STOP"}
_MANUAL_START_EVENTS = {"MANUAL_ADD_START"}
_MANUAL_END_EVENTS = {"MANUAL_ADD_END"}

# Состояния интервалов графика
STATE_ACTIVE = "active"
STATE_INACTIVE = "inactive"
STATE_MANUAL = "manual"

_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*\S+\s*\|\s*(\S+)"
)


def _format_dash(seconds) -> str:
    """Форматирует секунды; «—» если None или ноль для опциональных метрик."""
    if seconds is None:
        return "—"
    return format_duration(int(seconds))


def parse_report(filepath: str) -> dict | None:
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

    # Перерыв не входит в норму активности: активность считаем от
    # activity_norm_seconds, присутствие — от max_work_seconds. В отчётах до
    # появления перерыва поля нет — норма совпадает с рабочим временем.
    break_seconds = int(data.get("break_seconds") or 0)
    activity_norm_seconds = data.get("activity_norm_seconds")
    if not isinstance(activity_norm_seconds, int):
        activity_norm_seconds = max_work_seconds

    # Парные метрики «время + процент» собираем заранее, чтобы _show_window
    # оставался простым рендером.
    active_combined = combine_time_percent(active_seconds, activity_norm_seconds)
    work_combined = combine_time_percent(total_work_seconds, max_work_seconds)

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
        intervals = v2_intervals(data, date_obj)
        manual_intervals = manual_hour_intervals(events)
    else:
        intervals = build_intervals(events)
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
        "break_time": _format_dash(break_seconds),
        "activity_norm": _format_dash(activity_norm_seconds),
        "session_count": str(data.get("session_count") or 0),
        "events": events,
        "intervals": intervals,
        "manual_intervals": manual_intervals,
    }


def combine_time_percent(seconds, norm_seconds: int) -> str:
    """Форматирует «Xч Yм Zс (NN.N%)» по секундам и переданной норме.

    Норма у метрик разная: активность считается от нормы без перерыва,
    рабочее время — от полного. Возвращает «—», если seconds None или 0
    без нормы; без скобок — если нормы нет (поделить не на что).
    """
    if not seconds:
        return "—"
    time_str = format_duration(int(seconds))
    if norm_seconds <= 0:
        return time_str
    pct = calculate_activity_percent(int(seconds), norm_seconds / 3600)
    return f"{time_str} ({format_percent(pct)})"


def build_intervals(events: list[tuple[datetime.datetime, str]]) -> list[tuple[float, float, str]]:
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
    prev_hour = time_to_hours(events[0][0])

    for ts, event_type in events:
        hour = time_to_hours(ts)

        if hour > prev_hour:
            if is_manual:
                state = STATE_MANUAL
            else:
                state = STATE_ACTIVE if is_active else STATE_INACTIVE
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


def time_to_hours(dt: datetime.datetime) -> float:
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


def manual_hour_intervals(events: list) -> list:
    """Интервалы ручного времени (в часах) из пар MANUAL_ADD_START/END."""
    out = []
    start = None
    for ts, etype in sorted(events, key=lambda e: e[0]):
        if etype in _MANUAL_START_EVENTS:
            start = ts
        elif etype in _MANUAL_END_EVENTS and start is not None:
            out.append((time_to_hours(start), time_to_hours(ts)))
            start = None
    return out


def v2_intervals(data: dict, date_obj: datetime.date) -> list:
    """Точные интервалы активности/простоя из сырых sessions/idle (схема v2).

    Таймаут берётся текущий, для дня недели этой даты (`get_input_timeout`) —
    график отражает актуальную настройку, как и пересчитанное активное время.
    """
    sessions = _parse_iso_intervals(data.get("sessions"), "start", "end")
    timeout = get_input_timeout(date_obj)
    # Таймаут 0 — простой в этот день недели не считается: гэпы не рисуем.
    idle = _parse_iso_intervals(data.get("idle"), "from", "to") if timeout > 0 else []
    segments = activity_intervals.day_segments(sessions, idle, timeout, date_obj)
    day_start = datetime.datetime.combine(date_obj, datetime.time.min)
    result = []
    for seg_start, seg_end, state in segments:
        start_h = (seg_start - day_start).total_seconds() / 3600
        end_h = (seg_end - day_start).total_seconds() / 3600
        result.append((
            start_h, end_h,
            STATE_ACTIVE if state == "active" else STATE_INACTIVE,
        ))
    return result
