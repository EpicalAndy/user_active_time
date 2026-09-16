"""
Позиция окна конфигуратора между запусками: `widget_position.json` в LOG_DIR.

Файл — {"x", "y"}; ширина окна фиксированная, высота считается по содержимому,
поэтому хранить размер незачем. Сохранённая позиция применяется, только если
окно целиком помещается на экран (монитор могли отключить) — иначе окно
встаёт в правый нижний угол.
"""

import json
import os
import tkinter as tk

from config import LOG_DIR

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


def load_position() -> tuple[int, int] | None:
    """Сохранённая позиция виджета; None — файла нет или он битый."""
    try:
        with open(_WIDGET_POS_FILE, "r") as f:
            pos = json.load(f)
        return pos["x"], pos["y"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError, IOError):
        return None


def save_position(window: tk.Toplevel):
    """Сохраняет текущую позицию окна; ошибка записи не роняет виджет."""
    try:
        x = window.winfo_x()
        y = window.winfo_y()
        with open(_WIDGET_POS_FILE, "w") as f:
            json.dump({"x": x, "y": y}, f)
    except IOError:
        pass
