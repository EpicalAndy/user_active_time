"""
Монитор активности ввода (мышь/клавиатура) через низкоуровневые хуки Windows.

Регистрирует СЫРЫЕ гэпы простоя ввода [from, to] (без вычета таймаута) —
источник истины для пересчёта активного времени. Таймаут к гэпам применяется
позже, на стороне отчёта/статистики (см. modules/activity_intervals.py), поэтому
изменение таймаута пересчитывает уже прошедшую часть дня.

Живой статус (обратный отсчёт до простоя для виджета) считается здесь же по
текущему таймауту — это про «сейчас», не про запекание истории.
"""

import ctypes
import datetime
import threading
import time
from ctypes import wintypes

import config
from constants import MIN_IDLE_GAP_SECONDS
from utility import get_input_timeout, input_monitoring_enabled
from winapi import (
    HOOKPROC,
    kernel32,
    user32,
    WH_KEYBOARD_LL,
    WH_MOUSE_LL,
    WM_MOUSEMOVE,
    WM_QUIT,
)

# --- Состояние ввода (запись из hook-потока, чтение из timer-потока) ---
_last_input_mono: float = 0.0
_last_input_source: str = ""

# --- Состояние, управляемое timer-потоком и session-уведомлениями ---
_session_running: bool = False
_screen_locked: bool = False

# --- Якорь конвертации monotonic → wall-clock (фиксируется на старте сессии) ---
_mono0: float = 0.0
_wall0: datetime.datetime = datetime.datetime.now()

# --- Захват гэпов простоя ---
# _observed_input_mono — момент последнего «учтённого» ввода (начало текущего гэпа).
_observed_input_mono: float = 0.0
_closed_gaps: list[tuple[datetime.datetime, datetime.datetime]] = []
_gaps_lock = threading.Lock()

# --- Потоки и хуки ---
_hook_thread: threading.Thread | None = None
_timer_thread: threading.Thread | None = None
_hook_thread_id: int | None = None
_stop_event = threading.Event()

# --- Ссылки на callback-объекты хуков (prevent GC) ---
_kb_hook_proc = None
_mouse_hook_proc = None

# --- Точка расширения: фильтр ввода (инструмент «Блокировка ввода») ---
#
# Вызывается ПЕРВЫМ делом в hook-колбэках; вернул True — событие проглатывается
# и не уходит ни в систему, ни в учёт активности. Держится как callback, чтобы
# слой учёта не зависел от modules/tools (тот же приём, что с log_event).
#
# Больше про блокировку ввода учёт не знает ничего: проглоченное нажатие для
# него просто не случилось, а дальше время идёт как при обычном бездействии.
# Обязан быть таким же дешёвым, как сам колбэк: Windows снимает хук, который
# думает дольше ~300 мс.
INPUT_KIND_KEYBOARD = 0
INPUT_KIND_MOUSE = 1

_input_filter = None

# Слушатели начала/конца сессии (LOCK/UNLOCK/LOGON/LOGOFF).
_session_listeners: list = []


def _mono_to_wall(mono: float) -> datetime.datetime:
    """Переводит monotonic-метку в wall-clock через якорь сессии (точность ~1с)."""
    return _wall0 + datetime.timedelta(seconds=(mono - _mono0))


def _keyboard_hook_callback(nCode, wParam, lParam):
    """Callback низкоуровневого хука клавиатуры"""
    global _last_input_mono, _last_input_source
    if nCode >= 0:
        if _swallow(INPUT_KIND_KEYBOARD, wParam, lParam):
            return 1
        if _session_running and not _screen_locked:
            _last_input_source = "клавиатура"
            _last_input_mono = time.monotonic()
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


def _mouse_hook_callback(nCode, wParam, lParam):
    """Callback низкоуровневого хука мыши.

    `config.TRACK_MOUSE_MOVE` читается динамически при каждом событии,
    чтобы изменения настройки применялись без перезапуска приложения.
    """
    global _last_input_mono, _last_input_source
    if nCode >= 0:
        if _swallow(INPUT_KIND_MOUSE, wParam, lParam):
            return 1
        if _session_running and not _screen_locked:
            if wParam != WM_MOUSEMOVE or config.TRACK_MOUSE_MOVE:
                _last_input_source = "мышь"
                _last_input_mono = time.monotonic()
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


def _swallow(kind, wParam, lParam) -> bool:
    """Спрашивает у фильтра, проглотить ли событие. Ошибка фильтра = не глотать.

    Отказ «в сторону пропуска» намеренный: сломанный фильтр не должен оставить
    пользователя без клавиатуры.
    """
    if _input_filter is None:
        return False
    try:
        return _input_filter(kind, wParam, lParam)
    except Exception:
        return False


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
    """Поток таймера: раз в секунду закрывает завершённые гэпы простоя.

    Гэп фиксируется по факту возобновления ввода и не зависит от таймаута —
    таймаут применяется позже при вычислении активного времени.
    """
    global _observed_input_mono

    while not _stop_event.wait(timeout=1.0):
        if not _session_running or _screen_locked:
            continue

        cur = _last_input_mono
        if cur > _observed_input_mono:
            gap = cur - _observed_input_mono
            if gap >= MIN_IDLE_GAP_SECONDS:
                with _gaps_lock:
                    _closed_gaps.append(
                        (_mono_to_wall(_observed_input_mono), _mono_to_wall(cur))
                    )
            _observed_input_mono = cur


def start():
    """Запускает мониторинг ввода"""
    global _hook_thread, _timer_thread

    if not input_monitoring_enabled():
        print("[EVENTS] Мониторинг ввода отключен (таймаут 0 во все дни недели)")
        return

    _stop_event.clear()

    _hook_thread = threading.Thread(
        target=_hook_thread_func, daemon=True, name="InputHookThread"
    )
    _timer_thread = threading.Thread(
        target=_timer_thread_func, daemon=True, name="InputTimerThread"
    )

    _hook_thread.start()
    _timer_thread.start()

    print(f"[EVENTS] Мониторинг ввода запущен (таймауты по дням: {config.INPUT_ACTIVITY_TIMEOUT_BY_DAY})")


def stop():
    """Останавливает мониторинг ввода"""
    global _hook_thread, _timer_thread

    if not input_monitoring_enabled():
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


def set_input_filter(fn):
    """Ставит (или снимает, если None) фильтр ввода. См. `_input_filter`."""
    global _input_filter
    _input_filter = fn


def note_input(source: str):
    """Отмечает ввод, которого хук не увидел, — как будто он только что был.

    Нужна тому, кто проглатывает события фильтром: проглоченное нажатие в учёт
    не попадает, но само действие пользователя иногда вводом является. Так
    отмечается разблокировка ввода — момент, когда человек вернулся к работе.
    """
    global _last_input_mono, _last_input_source
    if not _session_running or _screen_locked:
        return
    _last_input_source = source
    _last_input_mono = time.monotonic()


def add_session_listener(fn):
    """Подписывает `fn(started: bool)` на начало/конец сессии (LOCK/UNLOCK).

    Колбэк вызывается в потоке монитора — переадресация в поток Tk на стороне
    подписчика.
    """
    _session_listeners.append(fn)


def _notify_session_listeners(started: bool):
    for fn in _session_listeners:
        try:
            fn(started)
        except Exception as e:
            print(f"[EVENTS] Ошибка слушателя сессии: {e}")


def drain_idle_gaps() -> list[tuple[datetime.datetime, datetime.datetime]]:
    """Возвращает и очищает закрытые гэпы простоя [from, to] (wall-clock)."""
    with _gaps_lock:
        gaps = _closed_gaps[:]
        _closed_gaps.clear()
    return gaps


def peek_idle_gaps() -> list[tuple[datetime.datetime, datetime.datetime]]:
    """Копия закрытых гэпов, ещё НЕ слитых в state.json (буфер не очищает).

    Гэп попадает в state.json только на ближайшем checkpoint, поэтому между
    его закрытием и checkpoint'ом он не виден ни в одном расчёте, читающем
    state (`stats.get_current_stats`). Для «живых» метрик такой гэп нужно
    подмешивать отсюда — иначе только что закончившийся простой на минуту
    исчезает из статистики и с таймлайна. Очищать буфер здесь нельзя: слить
    гэпы в состояние должен checkpoint, иначе они потеряются насовсем.
    """
    with _gaps_lock:
        return _closed_gaps[:]


def get_open_idle() -> tuple[datetime.datetime, datetime.datetime] | None:
    """Текущий незакрытый гэп простоя [from, now] или None, если мониторинг неактивен."""
    if not _session_running or _screen_locked:
        return None
    now_mono = time.monotonic()
    return (_mono_to_wall(_observed_input_mono), _mono_to_wall(now_mono))


def get_countdown_remaining() -> int | None:
    """Секунды до перехода в неактивность; 0 если уже неактивен; None если отключено."""
    if not _session_running or _screen_locked:
        return None
    # Таймаут — сегодняшний; ноль значит «сегодня простой не считается» —
    # отсчёта нет, как и в выключенном мониторинге.
    timeout = get_input_timeout(datetime.date.today())
    if timeout <= 0:
        return None
    last = max(_last_input_mono, _observed_input_mono)
    remaining = timeout - (time.monotonic() - last)
    return max(0, int(remaining))


def notify_session_start():
    """Вызывается при начале сессии (UNLOCK/LOGON). Сбрасывает состояние и якорь."""
    global _session_running, _screen_locked
    global _last_input_mono, _last_input_source
    global _mono0, _wall0, _observed_input_mono

    if not input_monitoring_enabled():
        return

    _mono0 = time.monotonic()
    _wall0 = datetime.datetime.now()
    _observed_input_mono = _mono0

    _screen_locked = False
    _session_running = True
    _last_input_mono = 0.0
    _last_input_source = ""

    with _gaps_lock:
        _closed_gaps.clear()

    print("[EVENTS] Сессия началась → захват гэпов простоя сброшен")
    _notify_session_listeners(True)


def notify_session_end():
    """Вызывается при завершении сессии (LOCK/LOGOFF). Финализирует открытый гэп."""
    global _session_running, _screen_locked, _observed_input_mono

    if not input_monitoring_enabled():
        return

    if _session_running:
        now_mono = time.monotonic()
        if now_mono - _observed_input_mono >= MIN_IDLE_GAP_SECONDS:
            with _gaps_lock:
                _closed_gaps.append(
                    (_mono_to_wall(_observed_input_mono), _mono_to_wall(now_mono))
                )
        _observed_input_mono = now_mono

    _screen_locked = True
    _session_running = False

    print("[EVENTS] Сессия завершена → мониторинг ввода приостановлен")
    _notify_session_listeners(False)
