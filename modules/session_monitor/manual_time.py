"""
Ручное добавление и удаление активного времени (диалог ⏱).

Ручной диапазон хранится не отдельным счётчиком, а парой событий
`MANUAL_ADD_START`/`MANUAL_ADD_END` в логе дня — активное время подтягивает его
при пересчёте (`activity.recompute_active`). Поэтому «добавить» и «удалить» —
это правка лога плюс пересчёт.

Куда писать, зависит от дня: сегодняшний/будущий живёт в `state.json`,
прошедший оттуда вычищен — для него источником истины служит дневной отчёт.
"""

import datetime

from utility import format_date_key, parse_date_key, parse_time
from . import session
from .activity import recompute_active
from .day_report import load_report_day_state, update_report
from .journal import manual_lines, parse_manual_entries
from .state_store import ensure_v2, fresh_day_state, get_day_state, load_state, save_state


def _manual_bounds(date_key: str, start_time: str, end_time: str):
    """(date, start_dt, end_dt, duration) для правки ручного диапазона."""
    date = parse_date_key(date_key)
    start_dt = datetime.datetime.combine(date, parse_time(start_time).time())
    end_dt = datetime.datetime.combine(date, parse_time(end_time).time())
    return date, start_dt, end_dt, int((end_dt - start_dt).total_seconds())


def _resolve_day_state(state: dict, date_key: str) -> tuple[dict, bool]:
    """Возвращает (day_state, in_state) для ручного редактирования дня.

    Сегодняшний/будущий день (или уже присутствующий, напр. незакрытая кросс-
    полуночная сессия) живёт в state.json — правки туда и сохраняются. Прошедший
    день оттуда вычищен, поэтому берём его из отчёта; state.json не трогаем, чтобы
    cleanup_old_days его снова не удалил, — durable-хранилищем служит сам отчёт.
    """
    today_key = format_date_key(datetime.date.today())
    if date_key in state or date_key >= today_key:
        return get_day_state(state, date_key), True
    return load_report_day_state(date_key) or fresh_day_state(), False


def add_manual_active_time(date_key: str, start_time: str, end_time: str, description: str):
    """Добавляет ручную запись активного времени за указанный день.

    start_time, end_time — строки формата HH:MM:SS (end > start, тот же день).
    Добавляет пару событий MANUAL_ADD_START/MANUAL_ADD_END в лог
    и увеличивает active_seconds. Лог-записи сортируются по времени.
    """
    date, start_dt, end_dt, duration = _manual_bounds(date_key, start_time, end_time)
    if duration <= 0:
        return

    start_line, end_line = manual_lines(start_dt, end_dt, description)

    with session.state_lock:
        state = load_state()
        day_state, in_state = _resolve_day_state(state, date_key)
        day_state["log_entries"].append(start_line)
        day_state["log_entries"].append(end_line)
        day_state["log_entries"].sort()
        # active_seconds — проекция; ручное время учитывается через пересчёт.
        day_state["active_seconds"] = recompute_active(day_state, date)
        if in_state:
            save_state(state)
        update_report(date_key, day_state)

    print(f"[MANUAL] {date_key} {start_time}—{end_time} (+{duration}с): {description}")


def get_manual_active_entries(date_key: str) -> list:
    """Возвращает список ручных записей активного времени за указанный день.

    Для прошедших дней (уже вычищенных из state.json) читает их из отчёта.
    """
    with session.state_lock:
        state = load_state()
        day_state = state.get(date_key)
        if day_state is None:
            day_state = load_report_day_state(date_key)
        if day_state is None:
            return []
        return parse_manual_entries(day_state.get("log_entries", []))


def remove_manual_active_time(date_key: str, start_time: str, end_time: str, description: str) -> bool:
    """Удаляет первую найденную ручную запись с указанными параметрами.

    Возвращает True, если запись найдена и удалена.
    """
    date, start_dt, end_dt, duration = _manual_bounds(date_key, start_time, end_time)
    if duration <= 0:
        return False

    start_line, end_line = manual_lines(start_dt, end_dt, description)

    with session.state_lock:
        state = load_state()
        in_state = date_key in state
        if in_state:
            day_state = state[date_key]
            ensure_v2(day_state)
        else:
            day_state = load_report_day_state(date_key)
            if day_state is None:
                return False

        log_entries = day_state.get("log_entries", [])
        try:
            log_entries.remove(start_line)
            log_entries.remove(end_line)
        except ValueError:
            return False

        day_state["active_seconds"] = recompute_active(day_state, date)
        if in_state:
            save_state(state)
        update_report(date_key, day_state)

    print(f"[MANUAL] Удалено {date_key} {start_time}—{end_time} (-{duration}с): {description}")
    return True
