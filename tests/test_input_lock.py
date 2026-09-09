"""
Тесты инструмента «Блокировка ввода».

Покрыто то, что не требует ни окон, ни хуков: разбор комбинации, распознавание
её нажатия и решение фильтра «глотать или пропустить». Именно здесь живут
свойства, ошибка в которых оставила бы пользователя без клавиатуры:
разблокировка должна срабатывать при зажатых ровно тех модификаторах, что
заданы, а до блокировки фильтр обязан пропускать всё, кроме самой комбинации.

Запуск: `python -m pytest tests/test_input_lock.py`
или как скрипт: `python tests/test_input_lock.py`.
"""

import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (  # noqa: E402
    KBDLLHOOKSTRUCT,
    VK_LCONTROL,
    VK_LMENU,
    VK_LSHIFT,
    VK_RCONTROL,
    VK_RSHIFT,
    WM_KEYDOWN,
)
from modules import events_monitor  # noqa: E402
from modules.events_monitor import (  # noqa: E402
    INPUT_KIND_KEYBOARD,
    INPUT_KIND_MOUSE,
)
import config  # noqa: E402
from modules.tools.input_lock import blocker  # noqa: E402
from modules.tools.input_lock.controller import InputLockTool  # noqa: E402
from modules.tools.spec import (  # noqa: E402
    SETTING_BOOL,
    SETTING_INT,
    SETTING_TEXT,
)
from modules.tools.input_lock.hotkey import (  # noqa: E402
    HotkeyMatcher,
    parse_hotkey,
)

VK_U = ord("U")
VK_A = ord("A")


# --- Разбор комбинации ---

def test_parse_full_hotkey():
    hotkey = parse_hotkey("ctrl+alt+shift+U")
    assert hotkey is not None
    assert hotkey.modifiers == {"ctrl", "alt", "shift"}
    assert hotkey.vk == VK_U
    assert hotkey.label == "Ctrl+Alt+Shift+U"


def test_parse_is_case_and_space_insensitive():
    assert parse_hotkey("  CTRL + Alt + u ").label == parse_hotkey("ctrl+alt+U").label


def test_parse_function_key():
    hotkey = parse_hotkey("win+F12")
    assert hotkey.vk == 0x7B and hotkey.label == "Win+F12"


def test_parse_rejects_hotkey_without_modifier():
    """Комбинация без модификатора отобрала бы клавишу у всех приложений сразу."""
    assert parse_hotkey("U") is None


def test_parse_rejects_garbage():
    assert parse_hotkey("") is None
    assert parse_hotkey("ctrl+") is None
    assert parse_hotkey("ctrl+alt") is None          # нет обычной клавиши
    assert parse_hotkey("ctrl+A+B") is None          # две обычные клавиши
    assert parse_hotkey("ctrl+нечто") is None


# --- Распознавание нажатия ---

def _matcher(text="ctrl+alt+shift+U"):
    return HotkeyMatcher(parse_hotkey(text))


def _press_modifiers(matcher, vks):
    for vk in vks:
        assert matcher.feed(vk, True) is False


def test_matcher_fires_on_full_combination():
    matcher = _matcher()
    _press_modifiers(matcher, [VK_LCONTROL, VK_LMENU, VK_LSHIFT])
    assert matcher.feed(VK_U, True) is True


def test_matcher_accepts_either_side_of_keyboard():
    """Хук всегда присылает конкретную сторону клавиши — обе должны подходить."""
    matcher = _matcher("ctrl+shift+U")
    _press_modifiers(matcher, [VK_RCONTROL, VK_RSHIFT])
    assert matcher.feed(VK_U, True) is True


def test_matcher_ignores_autorepeat():
    """Зажатая клавиша повторяется — но переключать блокировку надо один раз."""
    matcher = _matcher()
    _press_modifiers(matcher, [VK_LCONTROL, VK_LMENU, VK_LSHIFT])
    assert matcher.feed(VK_U, True) is True
    assert matcher.feed(VK_U, True) is False
    matcher.feed(VK_U, False)
    assert matcher.feed(VK_U, True) is True


def test_matcher_requires_exact_modifiers():
    matcher = _matcher("ctrl+alt+U")
    _press_modifiers(matcher, [VK_LCONTROL])
    assert matcher.feed(VK_U, True) is False          # не хватает Alt

    _press_modifiers(matcher, [VK_LMENU, VK_LSHIFT])
    assert matcher.feed(VK_U, True) is False          # лишний Shift

    matcher.feed(VK_LSHIFT, False)
    assert matcher.feed(VK_U, True) is True


def test_matcher_reset_forgets_held_keys():
    """После экрана блокировки отпускание клавиш до нас не доходит."""
    matcher = _matcher()
    _press_modifiers(matcher, [VK_LCONTROL, VK_LMENU, VK_LSHIFT])
    matcher.reset()
    assert matcher.feed(VK_U, True) is False


def test_matcher_without_hotkey_never_fires():
    matcher = HotkeyMatcher(None)
    _press_modifiers(matcher, [VK_LCONTROL, VK_LMENU, VK_LSHIFT])
    assert matcher.feed(VK_U, True) is False


# --- Решение фильтра ---

def _setup_blocker(locked=False, hotkey="ctrl+alt+shift+U"):
    fired = []
    blocker.set_hotkey(parse_hotkey(hotkey))
    blocker.set_hotkey_callback(lambda: fired.append(True))
    blocker.set_locked(locked)
    blocker.reset_keys()
    return fired


def test_filter_passes_everything_while_unlocked():
    _setup_blocker(locked=False)
    assert blocker.handle_key(VK_A, True) is False
    assert blocker.handle_key(VK_LCONTROL, True) is False
    assert blocker.handle_key(VK_A, True) is False     # Ctrl+A не ломается


def test_filter_swallows_only_the_combination_while_unlocked():
    """Хвост комбинации не должен долетать до активного приложения."""
    fired = _setup_blocker(locked=False)
    blocker.handle_key(VK_LCONTROL, True)
    blocker.handle_key(VK_LMENU, True)
    blocker.handle_key(VK_LSHIFT, True)
    assert blocker.handle_key(VK_U, True) is True
    assert fired == [True]


def test_filter_swallows_everything_while_locked():
    _setup_blocker(locked=True)
    assert blocker.handle_key(VK_A, True) is True
    assert blocker.handle_key(VK_A, False) is True
    assert blocker.handle_key(VK_LCONTROL, True) is True


def test_filter_still_catches_combination_while_locked():
    """Иначе разблокировать было бы нечем: обычные механизмы комбинацию не видят."""
    fired = _setup_blocker(locked=True)
    blocker.handle_key(VK_LCONTROL, True)
    blocker.handle_key(VK_LMENU, True)
    blocker.handle_key(VK_LSHIFT, True)
    assert blocker.handle_key(VK_U, True) is True
    assert fired == [True]


def test_filter_reads_vkcode_from_hook_payload():
    """Путь из hook-колбэка: lParam → vkCode. Ошибка здесь не ловится тестами логики."""
    _setup_blocker(locked=False)
    payload = KBDLLHOOKSTRUCT(vkCode=VK_LCONTROL, scanCode=0, flags=0, time=0, dwExtraInfo=None)
    lparam = ctypes.cast(ctypes.pointer(payload), ctypes.c_void_p).value

    assert blocker.input_filter(INPUT_KIND_KEYBOARD, WM_KEYDOWN, lparam) is False
    blocker.set_locked(True)
    assert blocker.input_filter(INPUT_KIND_KEYBOARD, WM_KEYDOWN, lparam) is True
    blocker.set_locked(False)


def test_filter_blocks_mouse_only_while_locked():
    """Мышь читать не нужно: в заблокированном состоянии глотается всё подряд."""
    _setup_blocker(locked=False)
    assert blocker.input_filter(INPUT_KIND_MOUSE, 0, 0) is False
    blocker.set_locked(True)
    assert blocker.input_filter(INPUT_KIND_MOUSE, 0, 0) is True
    blocker.set_locked(False)


# --- Учёт времени во время блокировки ---
#
# Правило простое: блокировка не меняет в учёте ничего. Время идёт так же, как
# если бы пользователь просто ничего не нажимал, — вплоть до ухода в простой.
# Отличий два: проглоченные нажатия отсчёт не сбрасывают, а разблокировка
# сбрасывает, потому что человек за клавиатурой к работе вернулся.

def _idle_for(seconds: int):
    """Сессия идёт, ввода не было `seconds` секунд."""
    events_monitor.notify_session_start()
    events_monitor._closed_gaps.clear()
    events_monitor._last_input_mono = time.monotonic() - seconds
    events_monitor._observed_input_mono = events_monitor._last_input_mono


def _blocked_keypress():
    """Прогоняет нажатие через настоящий hook-колбэк при заблокированном вводе."""
    payload = KBDLLHOOKSTRUCT(vkCode=VK_A, scanCode=0, flags=0, time=0, dwExtraInfo=None)
    lparam = ctypes.cast(ctypes.pointer(payload), ctypes.c_void_p).value
    events_monitor.set_input_filter(blocker.input_filter)
    try:
        return events_monitor._keyboard_hook_callback(0, WM_KEYDOWN, lparam)
    finally:
        events_monitor.set_input_filter(None)


def test_blocked_keypress_does_not_reset_the_idle_countdown():
    """Отсчёт до простоя идёт, как будто пользователь просто ничего не нажимает."""
    _setup_blocker(locked=True)
    _idle_for(60)
    before = events_monitor.get_countdown_remaining()

    swallowed = _blocked_keypress()

    assert swallowed == 1
    assert events_monitor.get_countdown_remaining() == before


def test_unlock_counts_as_activity():
    """Разблокировал — вернулся к работе: отсчёт стартует заново."""
    _idle_for(60)
    assert events_monitor.get_countdown_remaining() < config.INPUT_ACTIVITY_TIMEOUT

    events_monitor.note_input("клавиатура")

    assert events_monitor.get_countdown_remaining() == config.INPUT_ACTIVITY_TIMEOUT


def test_note_input_is_ignored_without_a_session():
    """На заблокированном экране ввода быть не может — выдумывать его нельзя."""
    _idle_for(60)
    events_monitor.notify_session_end()
    marker = events_monitor._last_input_mono

    events_monitor.note_input("клавиатура")

    assert events_monitor._last_input_mono == marker


# --- Схема настроек (вкладка «Инструменты») ---

def test_settings_schema_is_renderable():
    """Диалог рендерит вкладку по схеме — значит, схема обязана быть полной."""
    assert InputLockTool.SETTINGS
    for spec in InputLockTool.SETTINGS:
        assert spec["label"]
        assert spec.get("kind", SETTING_BOOL) in (SETTING_BOOL, SETTING_INT, SETTING_TEXT)


def test_settings_keys_exist_in_config():
    """Ключ схемы — имя параметра в config.py: опечатка уронила бы диалог."""
    for spec in InputLockTool.SETTINGS:
        assert hasattr(config, spec["key"]), spec["key"]


def test_settings_validation_guards_the_hotkey():
    """Комбинацию, которую нечем распознать, сохранять нельзя."""
    spec = next(s for s in InputLockTool.SETTINGS if s["key"] == "INPUT_LOCK_HOTKEY")
    validate = spec["validate"]

    assert validate("ctrl+alt+shift+U") is None
    title, text = validate("U")
    assert title and "U" in text


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
