"""
Фильтр ввода: решает, проглотить ли событие клавиатуры/мыши.

Живёт в hook-потоке `events_monitor` и вызывается на каждое событие ввода,
поэтому здесь нет ни I/O, ни блокировок — только сравнения целых и работа
с матчером комбинации. Всё тяжёлое (плашка, таймеры, логи) — в controller.py,
куда сюда уходит только «комбинация нажата» через колбэк.

Второй LL-хук специально не ставится: он умножил бы риск снятия хука по
таймауту и породил бы вопрос порядка в цепочке. Вместо этого приложение
переиспользует хуки, которые уже есть у монитора активности.
"""

import ctypes

from winapi import KBDLLHOOKSTRUCT, WM_KEYDOWN, WM_SYSKEYDOWN
from modules.events_monitor import INPUT_KIND_KEYBOARD

from .hotkey import HotkeyMatcher

_KBDLLHOOKSTRUCT_P = ctypes.POINTER(KBDLLHOOKSTRUCT)

# Флаг читается из hook-потока, пишется из потока Tk. Присваивание bool
# атомарно под GIL — тот же приём, что и с метками ввода в events_monitor.
_locked: bool = False

_matcher = HotkeyMatcher()
_on_hotkey = None


def set_hotkey(hotkey):
    """Задаёт комбинацию (объект Hotkey или None — тогда ловить нечего)."""
    _matcher.set_hotkey(hotkey)


def set_hotkey_callback(fn):
    """Колбэк «комбинация нажата». Вызывается в hook-потоке — переадресуй в Tk."""
    global _on_hotkey
    _on_hotkey = fn


def set_locked(locked: bool):
    global _locked
    _locked = locked


def is_locked() -> bool:
    return _locked


def reset_keys():
    """Забыть зажатые модификаторы (после возврата с экрана блокировки)."""
    _matcher.reset()


def handle_key(vk: int, is_down: bool) -> bool:
    """Логика клавиатуры: True — событие проглотить.

    Пока ввод не заблокирован, глотается ровно одно событие — нажатие самой
    комбинации: иначе активное приложение получило бы «хвост» от неё. Всё
    остальное проходит насквозь, чтобы обычные сочетания не ломались.
    """
    fired = _matcher.feed(vk, is_down)
    if fired:
        if _on_hotkey is not None:
            _on_hotkey()
        return True
    return _locked


def input_filter(kind, wParam, lParam) -> bool:
    """Точка входа из hook-колбэков events_monitor."""
    if kind != INPUT_KIND_KEYBOARD:
        return _locked

    vk = ctypes.cast(lParam, _KBDLLHOOKSTRUCT_P).contents.vkCode
    return handle_key(vk, wParam in (WM_KEYDOWN, WM_SYSKEYDOWN))
