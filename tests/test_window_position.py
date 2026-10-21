"""
Тесты файла окна конфигуратора (`modules/widget/position`) на временном файле.

Позиция и флаг «окно в трее» живут в одном `widget_position.json` и пишутся
в разные моменты (отпускание после перетаскивания и сворачивание/показ),
поэтому запись одного не должна затирать другое. Нет файла, битый файл или
не-bool во флаге — окно стартует на экране.

Запуск: `python -m pytest tests/test_window_position.py`
или как скрипт: `python tests/test_window_position.py`.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.widget import position  # noqa: E402


class _FakeWindow:
    def __init__(self, x: int, y: int):
        self._x, self._y = x, y

    def winfo_x(self) -> int:
        return self._x

    def winfo_y(self) -> int:
        return self._y


def _with_temp_file(test):
    """Подменяет путь файла на временный на время теста."""
    def wrapper():
        saved = position._WIDGET_POS_FILE
        with tempfile.TemporaryDirectory() as tmp:
            position._WIDGET_POS_FILE = os.path.join(tmp, "widget_position.json")
            try:
                test()
            finally:
                position._WIDGET_POS_FILE = saved
    wrapper.__name__ = test.__name__
    return wrapper


def _write_raw(text: str):
    with open(position._WIDGET_POS_FILE, "w", encoding="utf-8") as f:
        f.write(text)


@_with_temp_file
def test_defaults_without_file():
    assert position.load_position() is None
    assert position.load_in_tray() is False


@_with_temp_file
def test_in_tray_keeps_position():
    position.save_position(_FakeWindow(100, 200))
    position.save_in_tray(True)
    assert position.load_position() == (100, 200)
    assert position.load_in_tray() is True


@_with_temp_file
def test_position_keeps_in_tray():
    position.save_in_tray(True)
    position.save_position(_FakeWindow(5, 6))
    assert position.load_in_tray() is True
    assert position.load_position() == (5, 6)
    position.save_in_tray(False)
    assert position.load_in_tray() is False


@_with_temp_file
def test_old_file_without_flag():
    # Файл до появления флага — только координаты: окно на экране.
    _write_raw(json.dumps({"x": 10, "y": 20}))
    assert position.load_in_tray() is False
    assert position.load_position() == (10, 20)


@_with_temp_file
def test_broken_or_odd_file():
    _write_raw("{not json")
    assert position.load_in_tray() is False
    assert position.load_position() is None
    _write_raw(json.dumps({"in_tray": "yes"}))
    assert position.load_in_tray() is False
    _write_raw(json.dumps([1, 2]))
    assert position.load_in_tray() is False
    position.save_in_tray(True)  # поверх не-словаря — пишется заново
    assert position.load_in_tray() is True


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
