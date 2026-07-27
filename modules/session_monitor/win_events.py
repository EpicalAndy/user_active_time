"""
Windows-слой монитора: подписка на события сессии и цикл сообщений.

Скрытое окно + WTS-нотификации — единственный способ узнать о LOCK/UNLOCK/
LOGON/LOGOFF без прав администратора. Всё, что приходит в `wnd_proc`,
транслируется в операции жизненного цикла из `session.py`.

Здесь же `main()` — точка входа монитора (в приложении крутится в фоновом
потоке, см. main.py).
"""

import ctypes
import datetime
import os
import threading
from ctypes import wintypes

from config import LOG_DIR
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
from utility import format_date_key, format_duration
from . import session
from .checkpoint import start_checkpoint_timer, stop_checkpoint_timer
from .state_store import cleanup_old_days, load_state

_monitor_thread_id = None  # ID потока монитора для остановки


def request_stop():
    """Запрашивает остановку монитора (вызов из другого потока)"""
    if _monitor_thread_id is not None:
        user32.PostThreadMessageW(_monitor_thread_id, WM_QUIT, 0, 0)


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
        session.log_event(event_name)

        # Управление сессией
        if wparam in (WTS_SESSION_UNLOCK, WTS_SESSION_LOGON):
            session.start_session()
            events_monitor.notify_session_start()
        elif wparam in (WTS_SESSION_LOCK, WTS_SESSION_LOGOFF):
            events_monitor.notify_session_end()
            session.end_session()

    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


# Ссылку на колбэк держим на уровне модуля: без неё сборщик мусора освободит
# трамплин ctypes, и Windows вызовет освобождённую память.
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

    cleanup_old_days(session.session_start_time)
    session.recover_orphan_open_sessions()  # дотянуть сессии, оборванные сбоем питания
    session.log_event("MONITOR_START (запуск мониторинга)")
    session.start_session()
    events_monitor.start()
    events_monitor.notify_session_start()
    start_checkpoint_timer()

    hwnd = None
    try:
        hwnd = create_hidden_window()
        subscribe_to_session_events(hwnd)
        print("Мониторинг запущен. Для теста: Win+L\n")
        run_message_loop()

    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        stop_checkpoint_timer()
        events_monitor.notify_session_end()
        events_monitor.stop()
        session.end_session()
        session.log_event("MONITOR_STOP (остановка мониторинга)")
        if hwnd:
            wtsapi32.WTSUnRegisterSessionNotification(hwnd)
            user32.DestroyWindow(hwnd)
