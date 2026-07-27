"""
Пересчёт активного времени и таймлайна дня из сырых интервалов.

Активное время — не накопительный счётчик, а **проекция**: оно каждый раз
считается заново из `sessions`/`idle` с *текущим* `INPUT_ACTIVITY_TIMEOUT`
(ядро формулы — `modules/activity_intervals.py`). Поэтому изменение таймаута
пересчитывает и уже прошедшую часть дня.

Слагаемые дня: проекция сессий и простоя + ручное время из лога +
`legacy_base_seconds` (наследие записей схемы v1, см. `state_store.ensure_v2`).
"""

import datetime

import config
from modules import activity_intervals
from utility import parse_time
from .journal import manual_seconds, parse_manual_entries
from .state_store import parse_idle_intervals, parse_session_intervals


def _day_intervals(day_state: dict, live_open_session=None, extra_idle=()):
    """Интервалы дня (sessions, idle) с подмешанной открытой сессией и гэпом.

    Открытая (незакрытая) сессия учитывается так:
    - live_open_session=(старт, сейчас) — «живой» вариант до текущей секунды
      (для виджета); если задан, сохранённый open_session игнорируется;
    - иначе берётся сохранённый в state.json `open_session` (его конец = время
      последнего checkpoint) — он переживает сбой питания.
    extra_idle — открытый гэп простоя для «живого» расчёта.
    """
    sessions = parse_session_intervals(day_state.get("sessions", []))
    if live_open_session is not None:
        sessions.append(live_open_session)
    elif day_state.get("open_session"):
        sessions += parse_session_intervals([day_state["open_session"]])
    idle = parse_idle_intervals(day_state.get("idle", [])) + list(extra_idle)
    return sessions, idle


def recompute_active(day_state: dict, date, live_open_session=None, extra_idle=()) -> int:
    """Активное время дня = проекция от sessions/idle + ручное время + legacy-смещение."""
    sessions, idle = _day_intervals(day_state, live_open_session, extra_idle)
    base = activity_intervals.compute_active_seconds(
        sessions, idle, config.INPUT_ACTIVITY_TIMEOUT, date,
    )
    manual = manual_seconds(day_state.get("log_entries", []))
    return base + manual + day_state.get("legacy_base_seconds", 0)


def build_timeline(
    day_state: dict, date, span_start, span_end, live_open_session=None, extra_idle=(),
) -> dict | None:
    """Таймлайн дня для круговой диаграммы: границы дня + размеченные отрезки.

    Границы — это ровно метрика «Рабочее время»: [первый логин, сейчас]. Внутри
    них лежат отрезки из тех же сырых интервалов, что и активное время
    (`day_segments`), плюс ручные интервалы поверх — как в дневном отчёте.
    Всё, что в границы не попало, отрезается; непокрытая отрезками часть — простой
    (рисующая сторона считает её фоном).

    Возвращает {start_seconds, end_seconds, segments} в секундах от полуночи,
    где segments — [(start, end, "active"|"inactive"|"manual")] в порядке
    отрисовки (ручное время последним, т.е. поверх). None — рабочего времени
    за день ещё нет.
    """
    if span_end <= span_start:
        return None

    sessions, idle = _day_intervals(day_state, live_open_session, extra_idle)
    raw = list(activity_intervals.day_segments(
        sessions, idle, config.INPUT_ACTIVITY_TIMEOUT, date,
    ))
    for pair in parse_manual_entries(day_state.get("log_entries", [])):
        try:
            manual_start = datetime.datetime.combine(date, parse_time(pair["start"]).time())
            manual_end = datetime.datetime.combine(date, parse_time(pair["end"]).time())
        except ValueError:
            continue
        if manual_end > manual_start:
            raw.append((manual_start, manual_end, "manual"))

    day_start = datetime.datetime.combine(date, datetime.time.min)
    segments = []
    for seg_start, seg_end, kind in raw:
        start = max(seg_start, span_start)
        end = min(seg_end, span_end)
        if end > start:
            segments.append((
                int((start - day_start).total_seconds()),
                int((end - day_start).total_seconds()),
                kind,
            ))

    return {
        "start_seconds": int((span_start - day_start).total_seconds()),
        "end_seconds": int((span_end - day_start).total_seconds()),
        "segments": segments,
    }
