"""
Монитор активности ввода (мышь/клавиатура) через низкоуровневые хуки Windows.
Отслеживает неактивность пользователя по таймауту.
"""

import ctypes
import threading
import time
from ctypes import wintypes

from config import INPUT_ACTIVITY_TIMEOUT
from constants import (
    HOOKPROC,
    WH_KEYBOARD_LL,
    WH_MOUSE_LL,
    WM_QUIT,
    kernel32,
    user32,
)

# --- Состояние ввода (запись из hook-потока, чтение из timer-потока) ---
_last_input_mono: float = 0.0
_last_input_source: str = ""

# --- Состояние, управляемое timer-потоком и session-уведомлениями ---
_is_active: bool = False
_session_running: bool = False
_screen_locked: bool = False
_countdown_start_mono: float = 0.0

# --- Учёт неактивного времени за текущую сессию ---
_inactive_start_mono: float = 0.0
_total_inactive_seconds: float = 0.0

# --- Callback для логирования ---
_log_callback = None

# --- Потоки и хуки ---
_hook_thread: threading.Thread | None = None
_timer_thread: threading.Thread | None = None
_hook_thread_id: int | None = None
_stop_event = threading.Event()

# --- Ссылки на callback-объекты хуков (prevent GC) ---
_kb_hook_proc = None
_mouse_hook_proc = None


def _keyboard_hook_callback(nCode, wParam, lParam):
    """Callback низкоуровневого хука клавиатуры"""
    global _last_input_mono, _last_input_source
    if nCode >= 0 and _session_running and not _screen_locked:
        _last_input_source = "клавиатура"
        _last_input_mono = time.monotonic()
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


def _mouse_hook_callback(nCode, wParam, lParam):
    """Callback низкоуровневого хука мыши"""
    global _last_input_mono, _last_input_source
    if nCode >= 0 and _session_running and not _screen_locked:
        _last_input_source = "мышь"
        _last_input_mono = time.monotonic()
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


def _hook_thread_func():
    """Поток хуков: устанавливает LL-хуки и запускает message pump"""
    global _hook_thread_id, _kb_hook_proc, _mouse_hook_proc

    _hook_thread_id = threading.current_thread().ident

    _kb_hook_proc = HOOKPROC(_keyboard_hook_callback)
    _mouse_hook_proc = HOOKPROC(_mouse_hook_callback)

    hMod = kernel32.GetModuleHandleW(None)

    kb_hook = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, _kb_hook_proc, hMod, 0
    )
    mouse_hook = user32.SetWindowsHookExW(
        WH_MOUSE_LL, _mouse_hook_proc, hMod, 0
    )

    if not kb_hook:
        print("[EVENTS] Ошибка: не удалось установить хук клавиатуры")
    if not mouse_hook:
        print("[EVENTS] Ошибка: не удалось установить хук мыши")

    print("[EVENTS] Хуки ввода установлены")

    msg = wintypes.MSG()
    while True:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == 0 or ret == -1:
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    if kb_hook:
        user32.UnhookWindowsHookEx(kb_hook)
    if mouse_hook:
        user32.UnhookWindowsHookEx(mouse_hook)

    print("[EVENTS] Хуки ввода сняты")


def _timer_thread_func():
    """Поток таймера: проверяет таймаут неактивности каждую секунду"""
    global _is_active, _countdown_start_mono
    global _inactive_start_mono, _total_inactive_seconds

    timeout = INPUT_ACTIVITY_TIMEOUT

    while not _stop_event.wait(timeout=1.0):
        if not _session_running or _screen_locked:
            continue

        now_mono = time.monotonic()
        last_input = _last_input_mono

        # Был новый ввод с момента последнего сброса таймаута
        if last_input > _countdown_start_mono:
            _countdown_start_mono = last_input
            if not _is_active:
                # Переход: неактивен → активен
                _total_inactive_seconds += last_input - _inactive_start_mono
                _is_active = True
                source = _last_input_source or "неизвестно"
                if _log_callback:
                    _log_callback(f"INPUT_ACTIVE (активен, источник: {source})")
                print(f"[EVENTS] Активен (источник: {source})")

        # Таймаут истёк — пользователь неактивен
        if _is_active and (now_mono - _countdown_start_mono) >= timeout:
            # Переход: активен → неактивен
            _inactive_start_mono = _countdown_start_mono + timeout
            _is_active = False
            source = _last_input_source or "нет"
            if _log_callback:
                _log_callback(f"INPUT_INACTIVE (неактивен, последний: {source})")
            print(f"[EVENTS] Неактивен (таймаут {timeout}с, последний ввод: {source})")


def start(log_callback):
    """Запускает мониторинг ввода"""
    global _log_callback, _hook_thread, _timer_thread

    if INPUT_ACTIVITY_TIMEOUT <= 0:
        print("[EVENTS] Мониторинг ввода отключен (INPUT_ACTIVITY_TIMEOUT = 0)")
        return

    _log_callback = log_callback

    _stop_event.clear()

    _hook_thread = threading.Thread(
        target=_hook_thread_func, daemon=True, name="InputHookThread"
    )
    _timer_thread = threading.Thread(
        target=_timer_thread_func, daemon=True, name="InputTimerThread"
    )

    _hook_thread.start()
    _timer_thread.start()

    print(f"[EVENTS] Мониторинг ввода запущен (таймаут: {INPUT_ACTIVITY_TIMEOUT}с)")


def stop():
    """Останавливает мониторинг ввода"""
    global _hook_thread, _timer_thread

    if INPUT_ACTIVITY_TIMEOUT <= 0:
        return

    _stop_event.set()

    if _hook_thread_id is not None:
        user32.PostThreadMessageW(_hook_thread_id, WM_QUIT, 0, 0)

    if _timer_thread and _timer_thread.is_alive():
        _timer_thread.join(timeout=3)
    if _hook_thread and _hook_thread.is_alive():
        _hook_thread.join(timeout=3)

    _hook_thread = None
    _timer_thread = None

    print("[EVENTS] Мониторинг ввода остановлен")


def get_session_inactive_seconds() -> int:
    """Возвращает суммарное неактивное время (секунды) за текущую сессию"""
    if INPUT_ACTIVITY_TIMEOUT <= 0:
        return 0
    total = _total_inactive_seconds
    # Если сейчас неактивен — прибавляем текущий незавершённый период
    if not _is_active and _inactive_start_mono > 0 and _session_running:
        total += time.monotonic() - _inactive_start_mono
    return int(total)


def get_countdown_remaining() -> int | None:
    """Возвращает секунды до перехода в неактивное состояние, или None если отключено/неактивен"""
    if INPUT_ACTIVITY_TIMEOUT <= 0 or not _session_running or _screen_locked:
        return None
    if not _is_active:
        return 0
    elapsed = time.monotonic() - _countdown_start_mono
    remaining = INPUT_ACTIVITY_TIMEOUT - elapsed
    return max(0, int(remaining))


def notify_session_start():
    """Вызывается при начале сессии (UNLOCK/LOGON). Сбрасывает состояние."""
    global _is_active, _session_running, _screen_locked
    global _last_input_mono, _last_input_source, _countdown_start_mono
    global _inactive_start_mono, _total_inactive_seconds

    if INPUT_ACTIVITY_TIMEOUT <= 0:
        return

    _screen_locked = False
    _session_running = True
    _is_active = True
    _countdown_start_mono = time.monotonic()
    _last_input_mono = 0.0
    _last_input_source = ""
    _inactive_start_mono = 0.0
    _total_inactive_seconds = 0.0

    print("[EVENTS] Сессия началась → отсчёт активности сброшен")


def notify_session_end():
    """Вызывается при завершении сессии (LOCK/LOGOFF). Тихий сброс."""
    global _is_active, _session_running, _screen_locked, _total_inactive_seconds

    if INPUT_ACTIVITY_TIMEOUT <= 0:
        return

    # Финализируем текущий незавершённый период неактивности
    if not _is_active and _inactive_start_mono > 0:
        _total_inactive_seconds += time.monotonic() - _inactive_start_mono

    _screen_locked = True
    _session_running = False
    _is_active = False

    print("[EVENTS] Сессия завершена → мониторинг ввода приостановлен")
