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

from config import LOG_DIR, MAX_WORK_HOURS, STATE_FILE, USERNAME
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
from modules import events_monitor
from modules.report import write_report
from utility import (
    calculate_activity_percent,
    format_date_key,
    format_duration,
    format_time,
    format_timestamp,
    parse_date_key,
)

os.makedirs(LOG_DIR, exist_ok=True)


# === Отслеживание активного времени ===
session_start_time = None  # Когда началась текущая активная сессия
_monitor_thread_id = None  # ID потока монитора для остановки


def load_state() -> dict:
    """Загружает состояние из файла"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_state(state: dict):
    """Сохраняет состояние в файл"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_day_state(state: dict, date_key: str) -> dict:
    """Возвращает состояние дня, создавая если не существует"""
    if date_key not in state:
        state[date_key] = {
            "active_seconds": 0,
            "session_count": 0,
            "first_login": None,
            "last_logout": None,
            "log_entries": [],
        }
    return state[date_key]


def update_report(date_key: str, day_state: dict):
    """Обновляет файл отчёта для указанного дня"""
    write_report(
        log_dir=LOG_DIR,
        username=USERNAME,
        date=parse_date_key(date_key),
        active_seconds=day_state["active_seconds"],
        first_login=day_state["first_login"],
        last_logout=day_state["last_logout"],
        session_count=day_state["session_count"],
        log_entries=day_state["log_entries"],
    )


def get_current_stats() -> dict:
    """Возвращает текущую статистику за сегодня (включая незавершённую сессию)"""
    state = load_state()
    today = format_date_key(datetime.date.today())
    day_state = state.get(today, {"active_seconds": 0, "session_count": 0})

    active_seconds = day_state.get("active_seconds", 0)
    session_count = day_state.get("session_count", 0)

    # Добавляем время текущей незавершённой сессии (только сегодняшнюю часть)
    if session_start_time is not None:
        now = datetime.datetime.now()
        today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
        effective_start = max(session_start_time, today_start)
        elapsed = int((now - effective_start).total_seconds())
        # Вычитаем время неактивности ввода
        inactive = events_monitor.get_session_inactive_seconds()
        elapsed = max(0, elapsed - inactive)
        active_seconds += elapsed

    activity_percent = calculate_activity_percent(active_seconds, MAX_WORK_HOURS)

    return {
        "active_seconds": active_seconds,
        "session_count": session_count,
        "activity_percent": activity_percent,
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

    state = load_state()
    day_state = get_day_state(state, date_key)
    day_state["log_entries"].append(line)
    save_state(state)
    update_report(date_key, day_state)

    print(f"[LOG] {line}")


def start_session():
    """Начинает отсчёт активной сессии"""
    global session_start_time
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


def split_session_by_days(start_time, end_time):
    """Разбивает сессию по дням. Возвращает список (date_key, seconds, last_logout)"""
    segments = []
    current = start_time

    while current.date() < end_time.date():
        midnight = datetime.datetime.combine(
            current.date() + datetime.timedelta(days=1), datetime.time.min
        )
        duration = int((midnight - current).total_seconds())
        segments.append((format_date_key(current), duration, "23:59:59"))
        current = midnight

    duration = int((end_time - current).total_seconds())
    segments.append((format_date_key(end_time), duration, format_time(end_time)))

    return segments


def record_day_activity(day_state: dict, duration: int, last_logout: str):
    """Записывает активность сессии в состояние одного дня"""
    day_state["active_seconds"] += duration
    day_state["session_count"] += 1
    if day_state["first_login"] is None:
        day_state["first_login"] = "00:00:00"
    day_state["last_logout"] = last_logout


def end_session():
    """Завершает сессию и записывает время"""
    global session_start_time

    if session_start_time is None:
        print("[SESSION] Сессия не была начата, пропускаем")
        return

    end_time = datetime.datetime.now()
    inactive_seconds = events_monitor.get_session_inactive_seconds()

    state = load_state()
    segments = split_session_by_days(session_start_time, end_time)

    # Вычитаем неактивное время из сегментов (с конца)
    remaining_inactive = inactive_seconds
    for i in range(len(segments) - 1, -1, -1):
        if remaining_inactive <= 0:
            break
        date_key, duration, last_logout = segments[i]
        subtract = min(duration, remaining_inactive)
        segments[i] = (date_key, duration - subtract, last_logout)
        remaining_inactive -= subtract

    for date_key, duration, last_logout in segments:
        day_state = get_day_state(state, date_key)
        record_day_activity(day_state, duration, last_logout)
        print(f"[STATS] {date_key}: +{format_duration(duration)} "
              f"(всего: {format_duration(day_state['active_seconds'])})")

    save_state(state)

    for date_key, _, _ in segments:
        update_report(date_key, state[date_key])

    session_start_time = None


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

    log_event("MONITOR_START (запуск мониторинга)")
    start_session()
    events_monitor.start(log_callback=log_event)
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
