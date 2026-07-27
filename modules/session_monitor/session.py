"""
Жизненный цикл сессии и владелец изменяемого рантайма.

Здесь живут два разделяемых между потоками объекта:

- `session_start_time` — начало текущей активной сессии (None, если сессии нет);
- `state_lock` — защита `state.json` и `session_start_time` от гонок.

**Важно (та же конвенция, что у config/theme):** `session_start_time`
перепривязывается, поэтому читать его нужно динамически — `session.session_start_time`
через `import`-модуля, а НЕ `from .session import session_start_time` (последнее
навсегда запомнит значение на момент импорта). `state_lock` — объект, его можно
импортировать как угодно.

Лок НЕ реентрантный: публичные функции этого пакета берут его ровно один раз,
на верхнем уровне, и вызывают под ним только хелперы нижних слоёв
(state_store / journal / activity / day_report), которые лок не трогают.
"""

import datetime
import threading

from modules import events_monitor
from utility import format_date_key, format_duration, format_time, parse_date_key
from . import journal
from .activity import recompute_active
from .day_report import update_report
from .state_store import (
    add_interval_to_days,
    bump_last_logout,
    cleanup_old_days,
    ensure_v2,
    get_day_state,
    interval_item,
    iter_dates,
    load_state,
    save_state,
)

# === Разделяемый рантайм ===
session_start_time = None  # Когда началась текущая активная сессия
state_lock = threading.Lock()  # Защита state.json и session_start_time от гонок потоков

# Префиксы событий, завершающих рабочий день.
# LOCK сюда не включён: блокировка — короткий перерыв, и без того обновляет
# last_logout через end_session.
_TERMINAL_EVENT_PREFIXES = ("LOGOFF", "MONITOR_STOP")


def log_event(event_type: str):
    """Записывает событие в состояние и обновляет отчёт"""
    now = datetime.datetime.now()
    date_key = format_date_key(now)
    line = journal.event_line(now, event_type)

    with state_lock:
        state = load_state()
        day_state = get_day_state(state, date_key)
        day_state["log_entries"].append(line)

        # Завершающие события (LOGOFF, MONITOR_STOP) двигают конец рабочего дня
        # вперёд. Это важно, если MONITOR_STOP происходит после LOCK,
        # когда end_session уже ничего не обновляет.
        if event_type.startswith(_TERMINAL_EVENT_PREFIXES):
            bump_last_logout(day_state, format_time(now))

        save_state(state)
        update_report(date_key, day_state)

    print(f"[LOG] {line}")


def start_session():
    """Начинает отсчёт активной сессии"""
    global session_start_time

    with state_lock:
        session_start_time = datetime.datetime.now()

        date_key = format_date_key(session_start_time)
        time_str = format_time(session_start_time)

        state = load_state()
        day_state = get_day_state(state, date_key)

        if day_state["first_login"] is None:
            day_state["first_login"] = time_str

        # Регистрируем открытую сессию сразу — на случай сбоя питания она уже
        # в state.json (конец будет двигаться на каждом checkpoint).
        day_state["open_session"] = interval_item(
            (session_start_time, session_start_time), "start", "end",
        )
        day_state["active_seconds"] = recompute_active(day_state, session_start_time.date())
        save_state(state)
        update_report(date_key, day_state)

    print(f"[SESSION] Сессия началась: {time_str}")


def _drain_idle_into_state(state: dict):
    """Сливает закрытые гэпы простоя из монитора в состояние (intervals + лог)."""
    for gap_from, gap_to in events_monitor.drain_idle_gaps():
        item = interval_item((gap_from, gap_to), "from", "to")
        add_interval_to_days(state, gap_from, gap_to, "idle", item)
        day_state = get_day_state(state, format_date_key(gap_from))
        day_state["log_entries"].append(journal.idle_line(gap_from, gap_to))
        day_state["log_entries"].sort()


def checkpoint_session():
    """Промежуточное сохранение текущей сессии (защита от потери данных при сбое).

    active_seconds — проекция, поэтому пересчитывается «с нуля» из сохранённых
    интервалов плюс открытая сессия [старт, сейчас]. Открытую сессию ПЕРСИСТИМ в
    state.json (`open_session`), двигая её конец к «сейчас», — так при сбое
    питания теряется максимум один интервал checkpoint, а не вся сессия.
    """
    with state_lock:
        if session_start_time is None:
            return

        now = datetime.datetime.now()
        state = load_state()
        _drain_idle_into_state(state)

        # Открытую сессию храним целиком [старт, сейчас] в каждом затронутом дне
        # (пересечение с сутками делает формула пересчёта).
        open_session_item = interval_item((session_start_time, now), "start", "end")
        open_idle = events_monitor.get_open_idle()
        extra_idle = [open_idle] if open_idle else []
        live_idle = [interval_item(open_idle, "from", "to")] if open_idle else None

        affected = list(iter_dates(session_start_time, now))
        for day in affected:
            day_state = get_day_state(state, format_date_key(day))
            # Конец рабочего дня двигаем к «сейчас», чтобы метрика и рабочее
            # время отражали идущую сессию (не дожидаясь её закрытия).
            if day_state["first_login"] is None:
                day_state["first_login"] = (
                    format_time(session_start_time)
                    if day == session_start_time.date() else "00:00:00"
                )
            last_logout = format_time(now) if day == now.date() else "23:59:59"
            bump_last_logout(day_state, last_logout)
            day_state["open_session"] = open_session_item
            day_state["active_seconds"] = recompute_active(day_state, day, extra_idle=extra_idle)

        save_state(state)
        for day in affected:
            date_key = format_date_key(day)
            update_report(date_key, state[date_key], live_idle=live_idle)


def end_session():
    """Завершает сессию: фиксирует интервал сессии и пересчитывает активное время."""
    global session_start_time

    with state_lock:
        if session_start_time is None:
            print("[SESSION] Сессия не была начата, пропускаем")
            return

        end_time = datetime.datetime.now()
        open_start = session_start_time

        state = load_state()
        _drain_idle_into_state(state)

        # Сохраняем закрытый интервал сессии целиком в каждый затронутый день.
        session_item = interval_item((open_start, end_time), "start", "end")
        add_interval_to_days(state, open_start, end_time, "sessions", session_item)

        affected = list(iter_dates(open_start, end_time))
        for day in affected:
            day_state = get_day_state(state, format_date_key(day))
            # Сессия закрыта штатно — снимаем пометку открытой (теперь она в sessions).
            day_state.pop("open_session", None)
            day_state["session_count"] += 1
            if day_state["first_login"] is None:
                day_state["first_login"] = (
                    format_time(open_start) if day == open_start.date() else "00:00:00"
                )
            last_logout = format_time(end_time) if day == end_time.date() else "23:59:59"
            bump_last_logout(day_state, last_logout)
            day_state["active_seconds"] = recompute_active(day_state, day)
            print(f"[STATS] {format_date_key(day)}: "
                  f"{format_duration(day_state['active_seconds'])} активно")

        save_state(state)
        for day in affected:
            date_key = format_date_key(day)
            update_report(date_key, state[date_key])

        session_start_time = None
        cleanup_old_days(session_start_time)


def recover_orphan_open_sessions():
    """Финализирует сессии, не закрытые из-за сбоя (например, отключение питания).

    После жёсткого сброса `end_session` не отрабатывает, и открытая сессия
    остаётся помеченной `open_session` в state.json (с концом = время последнего
    checkpoint). При старте превращаем такие пометки в обычные закрытые сессии,
    чтобы наработанное время не потерялось. Вызывать ДО start_session.
    """
    with state_lock:
        state = load_state()
        recovered = []
        for date_key, day_state in state.items():
            orphan = day_state.get("open_session")
            if not orphan:
                continue
            ensure_v2(day_state)
            day_state.setdefault("sessions", []).append(orphan)
            day_state["session_count"] = day_state.get("session_count", 0) + 1
            line = journal.line(
                orphan.get("end", ""), "SESSION_RECOVERED (восстановлено после сбоя)",
            )
            day_state.setdefault("log_entries", []).append(line)
            day_state["log_entries"].sort()
            del day_state["open_session"]
            day_state["active_seconds"] = recompute_active(day_state, parse_date_key(date_key))
            recovered.append(date_key)

        if recovered:
            save_state(state)
            for date_key in recovered:
                update_report(date_key, state[date_key])
            print(f"[RECOVER] Восстановлены незакрытые сессии: {', '.join(sorted(recovered))}")
