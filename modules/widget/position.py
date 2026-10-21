"""
Окно конфигуратора между запусками: `widget_position.json` в LOG_DIR.

Файл — {"x", "y", "in_tray"}. Ширина окна фиксированная, высота считается
по содержимому, поэтому хранить размер незачем. Сохранённая позиция
применяется, только если окно целиком помещается на экран (монитор могли
отключить) — иначе окно встаёт в правый нижний угол.

`in_tray` — было ли окно спрятано в трей: при следующем запуске оно
стартует так же. Пишется в момент сворачивания и показа, а не на выходе:
при выключении компьютера приложение штатный выход не проходит.

Позиция и флаг пишутся независимо (чтение-правка-запись), чтобы одно не
затирало другое.
"""

import os
import tkinter as tk

from config import LOG_DIR
from modules.json_file import read_json, write_json_atomic

_WIDGET_POS_FILE = os.path.join(LOG_DIR, "widget_position.json")

# Отступы угла по умолчанию: от правого края и от нижнего (над панелью задач).
_DEFAULT_MARGIN_X = 20
_DEFAULT_MARGIN_Y = 60


def place_window(window: tk.Toplevel, width: int):
    """Ставит окно в сохранённую позицию или в правый нижний угол экрана."""
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    win_h = window.winfo_reqheight()

    saved = load_position()
    if saved:
        sx, sy = saved
        if 0 <= sx <= screen_w - width and 0 <= sy <= screen_h - win_h:
            window.geometry(f"{width}x{win_h}+{sx}+{sy}")
            return

    x = screen_w - width - _DEFAULT_MARGIN_X
    y = screen_h - win_h - _DEFAULT_MARGIN_Y
    window.geometry(f"{width}x{win_h}+{x}+{y}")


def _load() -> dict:
    data = read_json(_WIDGET_POS_FILE)
    return data if isinstance(data, dict) else {}


def _update(**fields):
    """Дописывает поля в файл, не трогая остальные; ошибка записи не роняет виджет."""
    try:
        write_json_atomic(_WIDGET_POS_FILE, {**_load(), **fields})
    except OSError:
        pass


def load_position() -> tuple[int, int] | None:
    """Сохранённая позиция виджета; None — файла нет или он битый."""
    pos = _load()
    try:
        return int(pos["x"]), int(pos["y"])
    except (TypeError, KeyError, ValueError):
        return None


def save_position(window: tk.Toplevel):
    """Сохраняет текущую позицию окна."""
    _update(x=window.winfo_x(), y=window.winfo_y())


def load_in_tray() -> bool:
    """Было ли окно спрятано в трей на момент последнего сворачивания/показа."""
    return _load().get("in_tray") is True


def save_in_tray(in_tray: bool):
    """Запоминает, спрятано ли окно в трей."""
    _update(in_tray=in_tray)
