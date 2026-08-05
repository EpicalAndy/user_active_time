"""
Текущая статистика за сегодня — то, что показывает виджет.

Единственная функция пакета, которую опрашивают из UI-потока. Работает только
на чтение: берёт `session.state_lock`, собирает снимок дня и отдаёт плоский
словарь метрик (плюс вложенный `timeline` для круговой диаграммы).
"""

import datetime

import config
from modules import events_monitor
from utility import (
    calculate_activity_percent,
    format_date_key,
    get_activity_norm_hours,
    get_break_hours,
    get_work_hours,
    parse_time,
)
from . import session
from .activity import build_timeline, recompute_active
from .state_store import ensure_v2, load_state


def get_current_stats() -> dict:
    """Возвращает текущую статистику за сегодня (включая незавершённую сессию)"""
    with session.state_lock:
        state = load_state()
        today_date = datetime.date.today()
        today = format_date_key(today_date)
        day_state = state.get(today, {})

        session_count = day_state.get("session_count", 0)
        now = datetime.datetime.now()
        # Читаем динамически: владелец значения — session.py (см. его шапку).
        session_start = session.session_start_time

        # Активное время — проекция от сырых интервалов с ТЕКУЩИМ таймаутом.
        # Незавершённую сессию и открытый гэп простоя подмешиваем как открытые
        # интервалы; формула сама обрежет их сегодняшней частью суток.
        live_open_session = None
        extra_idle = []
        if session_start is not None:
            ensure_v2(day_state)  # подтянуть legacy_base для старой записи (без сохранения)
            open_idle = events_monitor.get_open_idle()
            live_open_session = (session_start, now)
            extra_idle = [open_idle] if open_idle else []
            active_seconds = recompute_active(
                day_state, today_date,
                live_open_session=live_open_session,
                extra_idle=extra_idle,
            )
        else:
            active_seconds = day_state.get("active_seconds", 0)

        work_hours = get_work_hours(today_date)

        # Нерабочий день — возвращаем минимум данных
        if work_hours == 0:
            return {"is_working_day": False}

        # Две разные нормы: work_hours — сколько нужно присутствовать (общее
        # рабочее время), norm_hours — от чего считается 100% активности.
        norm_hours = get_activity_norm_hours(today_date)
        break_hours = get_break_hours(today_date)

        activity_percent = calculate_activity_percent(active_seconds, norm_hours)

        # Общее рабочее время (от первого логина до сейчас)
        full_day_seconds = 0
        timeline = None
        first_login = day_state.get("first_login")
        # Сессия началась до сегодня и продолжается — считаем логин с полуночи
        if first_login is None and session_start is not None and session_start.date() < today_date:
            first_login = "00:00:00"
        if first_login:
            login_time = datetime.datetime.combine(today_date, parse_time(first_login).time())
            full_day_seconds = max(0, int((now - login_time).total_seconds()))
            # Тот же отрезок [логин, сейчас], но с разбивкой на активность/простой.
            timeline = build_timeline(
                day_state, today_date, login_time, now,
                live_open_session=live_open_session,
                extra_idle=extra_idle,
            )

    activity_norm_seconds = int(norm_hours * 3600)
    break_seconds = int(break_hours * 3600)

    recommended_active_seconds = int(
        activity_norm_seconds * config.RECOMMENDED_ACTIVITY_THRESHOLD / 100
    )

    max_work_seconds = int(work_hours * 3600)

    # Расчётное время окончания дня = первый логин + норма (формат HH:MM).
    # Если за день ещё не было сессий — None.
    work_day_end = None
    if first_login and max_work_seconds > 0:
        login_dt = datetime.datetime.combine(today_date, parse_time(first_login).time())
        end_dt = login_dt + datetime.timedelta(seconds=max_work_seconds)
        work_day_end = end_dt.strftime("%H:%M")

    return {
        "is_working_day": True,
        "active_seconds": active_seconds,
        "session_count": session_count,
        "activity_percent": activity_percent,
        "full_day_seconds": full_day_seconds,
        "remaining_work_seconds": max(0, max_work_seconds - full_day_seconds),
        "recommended_remaining_seconds": max(0, recommended_active_seconds - active_seconds),
        "max_work_seconds": max_work_seconds,
        "activity_norm_seconds": activity_norm_seconds,
        "break_seconds": break_seconds,
        "work_day_end": work_day_end,
        "timeline": timeline,
    }
