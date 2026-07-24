"""
Значок приложения в системном трее (pystray).

Значок висит всё время работы приложения. Двойной клик по нему — открыть
(вернуть окно конфигуратора); правый клик — меню «Открыть / Выход».

pystray работает в собственном потоке (Icon.run блокирует), поэтому колбэки
`on_open`/`on_quit` вызываются НЕ в потоке Tk — вызывающая сторона обязана
переадресовать их в главный поток (например, через `root.after(0, ...)`).
"""

import threading

import pystray
from PIL import Image, ImageDraw

from constants import TRAY_MENU_OPEN, TRAY_MENU_QUIT, TRAY_TITLE
from modules import theme


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _make_image() -> Image.Image:
    """Значок: зелёное кольцо (перекликается с виджетом активности)."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = _hex_to_rgb(theme.COLOR_GREEN) + (255,)
    pad, width = 6, 10
    draw.ellipse([pad, pad, size - pad, size - pad], outline=color, width=width)
    return img


class TrayIcon:
    """Обёртка над pystray.Icon: всегда в трее, запуск/остановка в потоке."""

    def __init__(self, on_open, on_quit):
        self._on_open = on_open
        self._on_quit = on_quit
        self._thread: threading.Thread | None = None
        # default=True → пункт срабатывает по двойному клику (win32-бэкенд).
        self._icon = pystray.Icon(
            "user_active_time",
            _make_image(),
            TRAY_TITLE,
            menu=pystray.Menu(
                pystray.MenuItem(TRAY_MENU_OPEN, self._open, default=True),
                pystray.MenuItem(TRAY_MENU_QUIT, self._quit),
            ),
        )

    def _open(self, _icon=None, _item=None):
        self._on_open()

    def _quit(self, _icon=None, _item=None):
        self._on_quit()

    def start(self):
        self._thread = threading.Thread(
            target=self._icon.run, daemon=True, name="TrayIcon",
        )
        self._thread.start()

    def stop(self):
        try:
            self._icon.stop()
        except Exception:
            pass
