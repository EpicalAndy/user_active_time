"""
Монитор логинов/разлогинов пользователя Windows
Работает без прав администратора
"""

import ctypes
import datetime
import json
import os
import threading
from ctypes import wintypes

import config
from config import LOG_DIR, STATE_FILE, USERNAME
from constants import ENCODING
from constants import (
    NOTIFY_FOR_THIS_SESSION,
    WNDCLASSW,
    WNDPROC,
    WM_QUIT,
    WM_WTSSESSION_CHANGE,
    WTS_SESSION_LOCK,
    WTS_SESSION_LOGOFF,
    WTS_SESSION_LOGON,
    WTS_SESSION_UNLOCK,
    kernel32,
    user32,
    wtsapi32,
)
from modules import activity_intervals, events_monitor
from modules.report import write_report
from utility import (
    calculate_activity_percent,
    format_date_key,
    format_duration,
    format_time,
    format_timestamp,
    get_work_hours,
    parse_date_key,
    parse_time,
    parse_timestamp,
)

os.makedirs(LOG_DIR, exist_ok=True)


# === Отслеживание активного времени ===
session_start_time = None  # Когда началась текущая активная сессия
_monitor_thread_id = None  # ID потока монитора для остановки
_state_lock = threading.Lock()  # Защита state.json и session_start_time от гонок потоков

# Префиксы событий, завершающих рабочий день.
# LOCK сюда не включён: блокировка — короткий перерыв, и без того обновляет
# last_logout через end_session.
_TERMINAL_EVENT_PREFIXES = ("LOGOFF", "MONITOR_STOP")


def _bump_last_logout(day_state: dict, candidate: str):
    """Устанавливает last_logout в максимум из существующего и candidate."""
    existing = day_state.get("last_logout")
    if existing is None or candidate > existing:
        day_state["last_logout"] = candidate


def load_state() -> dict:
    """Загружает состояние из файла"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding=ENCODING) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_state(state: dict):
    """Сохраняет состояние в файл (атомарно через временный файл)"""
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w", encoding=ENCODING) as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, STATE_FILE)


def cleanup_old_days():
    """Удаляет из state.json данные за прошедшие дни после записи их отчётов.

    Не выполняет очистку, если текущая сессия началась до сегодня
    (кросс-полуночная сессия ещё не завершена).
    """
    if session_start_time is not None and session_start_time.date() < datetime.date.today():
        return

    today = format_date_key(datetime.date.today())
    state = load_state()
    old_keys = [key for key in state if key < today]
    if not old_keys:
        return
    for key in old_keys:
        del state[key]
    save_state(state)
    print(f"[STATE] Удалены устаревшие данные за: {', '.join(sorted(old_keys))}")


def _ensure_v2(day_state: dict):
    """Доводит запись дня до схемы v2 (sessions/idle/legacy_base_seconds).

    Для старой записи (v1) сохраняет уже накопленное active_seconds как
    legacy-смещение, вычитая ручное время, которое будет пересчитано из лога
    заново, — чтобы не задвоить его.
    """
    if "sessions" in day_state and "idle" in day_state:
        return
    existing_active = day_state.get("active_seconds", 0)
    day_state.setdefault("sessions", [])
    day_state.setdefault("idle", [])
    day_state["legacy_base_seconds"] = max(0, existing_active - _manual_seconds(day_state))


def get_day_state(state: dict, date_key: str) -> dict:
    """Возвращает состояние дня, создавая если не существует (схема v2)."""
    if date_key not in state:
        state[date_key] = {
            "active_seconds": 0,
            "session_count": 0,
            "first_login": None,
            "last_logout": None,
            "sessions": [],
            "idle": [],
            "legacy_base_seconds": 0,
            "log_entries": [],
        }
    else:
        _ensure_v2(state[date_key])
    return state[date_key]


def _parse_session_intervals(items: list) -> list:
    """Парсит [{"start","end"}] в список (datetime, datetime)."""
    out = []
    for it in items:
        try:
            out.append((parse_timestamp(it["start"]), parse_timestamp(it["end"])))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _parse_idle_intervals(items: list) -> list:
    """Парсит [{"from","to"}] в список (datetime, datetime)."""
    out = []
    for it in items:
        try:
            out.append((parse_timestamp(it["from"]), parse_timestamp(it["to"])))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _interval_item(interval, key_start: str, key_end: str) -> dict:
    """Сериализует (datetime, datetime) в {key_start, key_end} (TIMESTAMP-формат)."""
    start, end = interval
    return {key_start: format_timestamp(start), key_end: format_timestamp(end)}


def _manual_seconds(day_state: dict) -> int:
    """Суммарная длительность ручных интервалов из лога (MANUAL_ADD_START/END)."""
    total = 0
    for pair in _parse_manual_entries(day_state.get("log_entries", [])):
        try:
            start = parse_time(pair["start"])
            end = parse_time(pair["end"])
        except ValueError:
            continue
        total += max(0, int((end - start).total_seconds()))
    return total


def _recompute_active(day_state: dict, date, extra_sessions=(), extra_idle=()) -> int:
    """Активное время дня = проекция от sessions/idle + ручное время + legacy-смещение.

    extra_* — открытые (ещё не сохранённые) интервалы текущего момента:
    открытая сессия [старт, сейчас] и открытый гэп простоя.
    """
    sessions = _parse_session_intervals(day_state.get("sessions", [])) + list(extra_sessions)
    idle = _parse_idle_intervals(day_state.get("idle", [])) + list(extra_idle)
    base = activity_intervals.compute_active_seconds(
        sessions, idle, config.INPUT_ACTIVITY_TIMEOUT, date,
    )
    return base + _manual_seconds(day_state) + day_state.get("legacy_base_seconds", 0)


def _iter_dates(start_dt, end_dt):
    """Итерирует даты от start_dt.date() до end_dt.date() включительно."""
    day = start_dt.date()
    last = end_dt.date()
    while day <= last:
        yield day
        day += datetime.timedelta(days=1)


def _add_interval_to_days(state: dict, start_dt, end_dt, list_key: str, item: dict):
    """Добавляет интервал в список list_key каждого дня, который он покрывает.

    Интервал кладётся целиком (без обрезки) в каждый затронутый день — пересечение
    с границами суток делает уже формула пересчёта, в т.ч. корректно для форы таймаута.
    """
    for day in _iter_dates(start_dt, end_dt):
        get_day_state(state, format_date_key(day))[list_key].append(item)


def _append_idle_log(state: dict, gap_from, gap_to):
    """Добавляет человекочитаемую строку лога на закрытый гэп простоя."""
    line = (
        f"{format_timestamp(gap_from)} | {USERNAME} | "
        f"IDLE (простой до {format_time(gap_to)})"
    )
    day_state = get_day_state(state, format_date_key(gap_from))
    day_state["log_entries"].append(line)
    day_state["log_entries"].sort()


def update_report(date_key: str, day_state: dict, live_sessions=None, live_idle=None):
    """Обновляет файл отчёта для указанного дня.

    live_sessions/live_idle — открытые (ещё не закрытые) интервалы текущей
    сессии: записываются в файл, чтобы график/активность отражали идущую сессию,
    но НЕ сохраняются в state.json (иначе при следующем пересчёте задвоятся).
    """
    sessions = list(day_state.get("sessions", []))
    idle = list(day_state.get("idle", []))
    if live_sessions:
        sessions += live_sessions
    if live_idle:
        idle += live_idle
    write_report(
        log_dir=LOG_DIR,
        username=USERNAME,
        date=parse_date_key(date_key),
        active_seconds=day_state["active_seconds"],
        first_login=day_state["first_login"],
        last_logout=day_state["last_logout"],
        session_count=day_state["session_count"],
        log_entries=day_state["log_entries"],
        sessions=sessions,
        idle=idle,
    )


def get_current_stats() -> dict:
    """Возвращает текущую статистику за сегодня (включая незавершённую сессию)"""
    with _state_lock:
        state = load_state()
        today_date = datetime.date.today()
        today = format_date_key(today_date)
        day_state = state.get(today, {})

        session_count = day_state.get("session_count", 0)

        # Активное время — проекция от сырых интервалов с ТЕКУЩИМ таймаутом.
        # Незавершённую сессию и открытый гэп простоя подмешиваем как открытые
        # интервалы; формула сама обрежет их сегодняшней частью суток.
        if session_start_time is not None:
            _ensure_v2(day_state)  # подтянуть legacy_base для старой записи (без сохранения)
            now = datetime.datetime.now()
            open_idle = events_monitor.get_open_idle()
            active_seconds = _recompute_active(
                day_state, today_date,
                extra_sessions=[(session_start_time, now)],
                extra_idle=[open_idle] if open_idle else [],
            )
        else:
            active_seconds = day_state.get("active_seconds", 0)

        work_hours = get_work_hours(datetime.date.today())

        # Нерабочий день — возвращаем минимум данных
        if work_hours == 0:
            return {"is_working_day": False}

        activity_percent = calculate_activity_percent(active_seconds, work_hours)

        # Общее рабочее время (от первого логина до сейчас)
        full_day_seconds = 0
        first_login = day_state.get("first_login")
        # Сессия началась до сегодня и продолжается — считаем логин с полуночи
        if first_login is None and session_start_time is not None and session_start_time.date() < datetime.date.today():
            first_login = "00:00:00"
        if first_login:
            now = datetime.datetime.now()
            login_time = datetime.datetime.combine(datetime.date.today(), parse_time(first_login).time())
            full_day_seconds = max(0, int((now - login_time).total_seconds()))

    recommended_active_seconds = int(work_hours * 3600 * config.RECOMMENDED_ACTIVITY_THRESHOLD / 100)

    max_work_seconds = int(work_hours * 3600)

    # Расчётное время окончания дня = первый логин + норма (формат HH:MM).
    # Если за день ещё не было сессий — None.
    work_day_end = None
    if first_login and max_work_seconds > 0:
        login_dt = datetime.datetime.combine(
            datetime.date.today(), parse_time(first_login).time(),
        )
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
        "work_day_end": work_day_end,
    }


def request_stop():
    """Запрашивает остановку монитора (вызов из другого потока)"""
    if _monitor_thread_id is not None:
        user32.PostThreadMessageW(_monitor_thread_id, WM_QUIT, 0, 0)


def log_event(event_type: str):
    """Записывает событие в состояние и обновляет отчёт"""
    now = datetime.datetime.now()
    date_key = format_date_key(now)
    line = f"{format_timestamp(now)} | {USERNAME} | {event_type}"

    with _state_lock:
        state = load_state()
        day_state = get_day_state(state, date_key)
        day_state["log_entries"].append(line)

        # Завершающие события (LOGOFF, MONITOR_STOP) двигают конец рабочего дня
        # вперёд. Это важно, если MONITOR_STOP происходит после LOCK,
        # когда end_session уже ничего не обновляет.
        if event_type.startswith(_TERMINAL_EVENT_PREFIXES):
            _bump_last_logout(day_state, format_time(now))

        save_state(state)
        update_report(date_key, day_state)

    print(f"[LOG] {line}")


def add_manual_active_time(date_key: str, start_time: str, end_time: str, description: str):
    """Добавляет ручную запись активного времени за указанный день.

    start_time, end_time — строки формата HH:MM:SS (end > start, тот же день).
    Добавляет пару событий MANUAL_ADD_START/MANUAL_ADD_END в лог
    и увеличивает active_seconds. Лог-записи сортируются по времени.
    """
    date = parse_date_key(date_key)
    start_dt = datetime.datetime.combine(date, parse_time(start_time).time())
    end_dt = datetime.datetime.combine(date, parse_time(end_time).time())
    duration = int((end_dt - start_dt).total_seconds())
    if duration <= 0:
        return

    start_line = f"{format_timestamp(start_dt)} | {USERNAME} | MANUAL_ADD_START ({description})"
    end_line = f"{format_timestamp(end_dt)} | {USERNAME} | MANUAL_ADD_END ({description})"

    with _state_lock:
        state = load_state()
        day_state = get_day_state(state, date_key)
        day_state["log_entries"].append(start_line)
        day_state["log_entries"].append(end_line)
        day_state["log_entries"].sort()
        # active_seconds — проекция; ручное время учитывается через пересчёт.
        day_state["active_seconds"] = _recompute_active(day_state, date)
        save_state(state)
        update_report(date_key, day_state)

    print(f"[MANUAL] {date_key} {start_time}—{end_time} (+{duration}с): {description}")


def _parse_manual_entries(log_entries: list) -> list:
    """Извлекает пары MANUAL_ADD_START/END из лога.

    Возвращает список словарей с ключами start, end, description (HH:MM:SS).
    Сопоставляет каждый START с ближайшим последующим END с тем же описанием.
    """
    pending_starts = []
    pairs = []
    for line in log_entries:
        parts = line.split(" | ", 2)
        if len(parts) != 3:
            continue
        ts_str, _, event = parts
        if " " not in ts_str:
            continue
        time_str = ts_str.split(" ", 1)[1]
        if event.startswith("MANUAL_ADD_START (") and event.endswith(")"):
            desc = event[len("MANUAL_ADD_START ("):-1]
            pending_starts.append((time_str, desc))
        elif event.startswith("MANUAL_ADD_END (") and event.endswith(")"):
            desc = event[len("MANUAL_ADD_END ("):-1]
            for i, (s_time, s_desc) in enumerate(pending_starts):
                if s_desc == desc and s_time < time_str:
                    pairs.append({
                        "start": s_time,
                        "end": time_str,
                        "description": desc,
                    })
                    pending_starts.pop(i)
                    break
    return pairs


def get_manual_active_entries(date_key: str) -> list:
    """Возвращает список ручных записей активного времени за указанный день."""
    with _state_lock:
        state = load_state()
        day_state = state.get(date_key)
        if day_state is None:
            return []
        return _parse_manual_entries(day_state.get("log_entries", []))


def remove_manual_active_time(date_key: str, start_time: str, end_time: str, description: str) -> bool:
    """Удаляет первую найденную ручную запись с указанными параметрами.

    Возвращает True, если запись найдена и удалена.
    """
    date = parse_date_key(date_key)
    start_dt = datetime.datetime.combine(date, parse_time(start_time).time())
    end_dt = datetime.datetime.combine(date, parse_time(end_time).time())
    duration = int((end_dt - start_dt).total_seconds())
    if duration <= 0:
        return False

    start_line = f"{format_timestamp(start_dt)} | {USERNAME} | MANUAL_ADD_START ({description})"
    end_line = f"{format_timestamp(end_dt)} | {USERNAME} | MANUAL_ADD_END ({description})"

    with _state_lock:
        state = load_state()
        day_state = state.get(date_key)
        if day_state is None:
            return False

        _ensure_v2(day_state)
        log_entries = day_state.get("log_entries", [])
        try:
            log_entries.remove(start_line)
            log_entries.remove(end_line)
        except ValueError:
            return False

        day_state["active_seconds"] = _recompute_active(day_state, date)
        save_state(state)
        update_report(date_key, day_state)

    print(f"[MANUAL] Удалено {date_key} {start_time}—{end_time} (-{duration}с): {description}")
    return True


def start_session():
    """Начинает отсчёт активной сессии"""
    global session_start_time

    with _state_lock:
        session_start_time = datetime.datetime.now()

        date_key = format_date_key(session_start_time)
        time_str = format_time(session_start_time)

        state = load_state()
        day_state = get_day_state(state, date_key)

        if day_state["first_login"] is None:
            day_state["first_login"] = time_str
            save_state(state)
            update_report(date_key, day_state)

    print(f"[SESSION] Сессия началась: {time_str}")


def _drain_idle_into_state(state: dict):
    """Сливает закрытые гэпы простоя из монитора в состояние (intervals + лог)."""
    for gap_from, gap_to in events_monitor.drain_idle_gaps():
        item = _interval_item((gap_from, gap_to), "from", "to")
        _add_interval_to_days(state, gap_from, gap_to, "idle", item)
        _append_idle_log(state, gap_from, gap_to)


def checkpoint_session():
    """Промежуточное сохранение текущей сессии (защита от потери данных при сбое).

    active_seconds — проекция, поэтому пересчитывается «с нуля» из сохранённых
    интервалов плюс открытая сессия [старт, сейчас]. Старт сессии НЕ сдвигаем:
    пересчёт идемпотентен и не задваивает время.
    """
    with _state_lock:
        if session_start_time is None:
            return

        now = datetime.datetime.now()
        state = load_state()
        _drain_idle_into_state(state)

        open_session = (session_start_time, now)
        open_idle = events_monitor.get_open_idle()
        extra_idle = [open_idle] if open_idle else []

        affected = list(_iter_dates(session_start_time, now))
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
            _bump_last_logout(day_state, last_logout)
            day_state["active_seconds"] = _recompute_active(
                day_state, day,
                extra_sessions=[open_session],
                extra_idle=extra_idle,
            )

        save_state(state)

        # В файл отчёта пишем открытую сессию/гэп как live-интервалы, чтобы
        # график и активное время отражали идущую сессию (в state.json их нет).
        live_sessions = [_interval_item(open_session, "start", "end")]
        live_idle = [_interval_item(open_idle, "from", "to")] if open_idle else None
        for day in affected:
            date_key = format_date_key(day)
            update_report(date_key, state[date_key],
                          live_sessions=live_sessions, live_idle=live_idle)


def end_session():
    """Завершает сессию: фиксирует интервал сессии и пересчитывает активное время."""
    global session_start_time

    with _state_lock:
        if session_start_time is None:
            print("[SESSION] Сессия не была начата, пропускаем")
            return

        end_time = datetime.datetime.now()
        open_start = session_start_time

        state = load_state()
        _drain_idle_into_state(state)

        # Сохраняем закрытый интервал сессии целиком в каждый затронутый день.
        session_item = _interval_item((open_start, end_time), "start", "end")
        _add_interval_to_days(state, open_start, end_time, "sessions", session_item)

        affected = list(_iter_dates(open_start, end_time))
        for day in affected:
            day_state = get_day_state(state, format_date_key(day))
            day_state["session_count"] += 1
            if day_state["first_login"] is None:
                day_state["first_login"] = (
                    format_time(open_start) if day == open_start.date() else "00:00:00"
                )
            last_logout = format_time(end_time) if day == end_time.date() else "23:59:59"
            _bump_last_logout(day_state, last_logout)
            day_state["active_seconds"] = _recompute_active(day_state, day)
            print(f"[STATS] {format_date_key(day)}: "
                  f"{format_duration(day_state['active_seconds'])} активно")

        save_state(state)
        for day in affected:
            date_key = format_date_key(day)
            update_report(date_key, state[date_key])

        session_start_time = None
        cleanup_old_days()


def wnd_proc(hwnd, msg, wparam, lparam):
    """Обработчик сообщений окна"""
    if msg == WM_WTSSESSION_CHANGE:
        events = {
            WTS_SESSION_LOCK: "LOCK (блокировка)",
            WTS_SESSION_UNLOCK: "UNLOCK (разблокировка)",
            WTS_SESSION_LOGON: "LOGON (вход)",
            WTS_SESSION_LOGOFF: "LOGOFF (выход)",
        }
        event_name = events.get(wparam, f"UNKNOWN ({wparam})")
        log_event(event_name)

        # Управление сессией
        if wparam in (WTS_SESSION_UNLOCK, WTS_SESSION_LOGON):
            start_session()
            events_monitor.notify_session_start()
        elif wparam in (WTS_SESSION_LOCK, WTS_SESSION_LOGOFF):
            events_monitor.notify_session_end()
            end_session()

    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


wnd_proc_callback = WNDPROC(wnd_proc)


def register_window_class(class_name, hInstance):
    """Регистрирует класс окна для получения системных сообщений"""
    wnd_class = WNDCLASSW()
    wnd_class.style = 0
    wnd_class.lpfnWndProc = wnd_proc_callback
    wnd_class.cbClsExtra = 0
    wnd_class.cbWndExtra = 0
    wnd_class.hInstance = hInstance
    wnd_class.hIcon = None
    wnd_class.hCursor = None
    wnd_class.hbrBackground = None
    wnd_class.lpszMenuName = None
    wnd_class.lpszClassName = class_name

    class_atom = user32.RegisterClassW(ctypes.byref(wnd_class))
    if not class_atom:
        raise ctypes.WinError(ctypes.get_last_error())
    return class_atom


def create_hidden_window():
    """Создаёт скрытое окно для получения системных сообщений"""
    hInstance = kernel32.GetModuleHandleW(None)
    class_name = "SessionMonitor_" + str(os.getpid())

    register_window_class(class_name, hInstance)

    hwnd = user32.CreateWindowExW(
        0, class_name, "Session Monitor", 0,
        0, 0, 0, 0, None, None, hInstance, None
    )

    if not hwnd:
        error = ctypes.get_last_error()
        if error:
            raise ctypes.WinError(error)
        raise RuntimeError("CreateWindowExW вернул NULL")

    return hwnd


def print_today_stats():
    """Показывает статистику за сегодня"""
    state = load_state()
    today = format_date_key(datetime.date.today())
    day_state = state.get(today, {})
    seconds = day_state.get("active_seconds", 0)
    print(f"Активное время сегодня: {format_duration(seconds)}")


def subscribe_to_session_events(hwnd):
    """Подписывается на события сессии Windows"""
    result = wtsapi32.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION)
    if result:
        print("Подписка на события сессии: ОК")
    else:
        print("Предупреждение: не удалось подписаться на события")


def run_message_loop():
    """Запускает цикл обработки сообщений Windows"""
    msg = wintypes.MSG()
    while True:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == 0 or ret == -1:
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def main():
    global _monitor_thread_id
    _monitor_thread_id = threading.current_thread().ident

    print("=== Монитор сессий Windows ===")
    print(f"Папка логов: {LOG_DIR}")
    print()
    print_today_stats()
    print()
    print("Нажмите Ctrl+C для выхода\n")

    cleanup_old_days()
    log_event("MONITOR_START (запуск мониторинга)")
    start_session()
    events_monitor.start()
    events_monitor.notify_session_start()

    hwnd = None
    try:
        hwnd = create_hidden_window()
        subscribe_to_session_events(hwnd)
        print("Мониторинг запущен. Для теста: Win+L\n")
        run_message_loop()

    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        events_monitor.notify_session_end()
        events_monitor.stop()
        end_session()
        log_event("MONITOR_STOP (остановка мониторинга)")
        if hwnd:
            wtsapi32.WTSUnRegisterSessionNotification(hwnd)
            user32.DestroyWindow(hwnd)


if __name__ == "__main__":
    main()
