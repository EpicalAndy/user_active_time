"""
Тесты автозагрузки (`modules/autostart`) без записи в настоящий реестр.

Проверяется команда запуска (без консоли, пути в кавычках), разбор флага
«выключено в Диспетчере задач» и решение `apply`, когда реестр трогать:
только при смене состояния или если запись указывает на пропавшие файлы,
но не поверх рабочей записи другой копии приложения.

Запуск: `python -m pytest tests/test_autostart.py`
или как скрипт: `python tests/test_autostart.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import autostart  # noqa: E402


def test_launch_command_runs_main_without_console():
    command = autostart.launch_command()
    paths = autostart.command_paths(command)
    assert len(paths) == 2
    interpreter, script = paths
    assert os.path.basename(script) == "main.py"
    assert os.path.exists(script)
    # pythonw — если он есть рядом с интерпретатором (в venv он есть всегда).
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if os.path.exists(pythonw):
        assert interpreter == pythonw


def test_command_paths_handles_spaces():
    command = r'"C:\Program Files\py\pythonw.exe" "D:\My Projects\app\main.py"'
    assert autostart.command_paths(command) == [
        r"C:\Program Files\py\pythonw.exe",
        r"D:\My Projects\app\main.py",
    ]


def test_disabled_flag():
    enabled = bytes([0x02]) + bytes(11)
    enabled_alt = bytes([0x06]) + bytes(11)
    disabled = bytes([0x03]) + bytes(11)
    assert not autostart.is_disabled_flag(None)
    assert not autostart.is_disabled_flag(b"")
    assert not autostart.is_disabled_flag(enabled)
    assert not autostart.is_disabled_flag(enabled_alt)
    assert autostart.is_disabled_flag(disabled)


def _apply_with(enabled_now: bool, command: str | None, wanted: bool) -> list[bool]:
    """Вызывает apply на подменённом реестре; возвращает вызовы set_enabled."""
    calls: list[bool] = []
    saved = (autostart.is_enabled, autostart.registered_command, autostart.set_enabled)
    autostart.is_enabled = lambda: enabled_now
    autostart.registered_command = lambda: command
    autostart.set_enabled = calls.append
    try:
        autostart.apply(wanted)
    finally:
        autostart.is_enabled, autostart.registered_command, autostart.set_enabled = saved
    return calls


def test_apply_changes_state():
    assert _apply_with(False, None, True) == [True]
    assert _apply_with(True, autostart.launch_command(), False) == [False]


def test_apply_keeps_unchanged_state():
    assert _apply_with(False, None, False) == []
    assert _apply_with(True, autostart.launch_command(), True) == []


def test_apply_keeps_other_working_copy():
    # Запись другой копии с существующими файлами — не перезаписываем от «OK».
    other = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
    assert _apply_with(True, other, True) == []


def test_apply_repairs_moved_folder():
    stale = r'"Z:\nowhere\pythonw.exe" "Z:\nowhere\main.py"'
    assert _apply_with(True, stale, True) == [True]


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
