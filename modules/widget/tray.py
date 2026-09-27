"""
Значок приложения в системном трее (pystray).

Значок висит всё время работы приложения. Двойной клик по нему — открыть
(вернуть окно конфигуратора); правый клик — меню «Открыть / Выход».

pystray работает в собственном потоке (Icon.run блокирует), поэтому колбэки
`on_open`/`on_quit` вызываются НЕ в потоке Tk — вызывающая сторона обязана
переадресовать их в главный поток (например, через `root.after(0, ...)`).

pystray и Pillow — единственные внешние зависимости приложения. Если их нет,
модуль всё равно импортируется, а `create_tray` возвращает None: приложение
работает без трея.
"""

import sys
import threading

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception as e:  # noqa: BLE001 — любая поломка зависимости = без трея
    pystray = None
    _IMPORT_ERROR = e

from texts import TRAY_MENU_OPEN, TRAY_MENU_QUIT, TRAY_TITLE
from modules import theme


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# Зоны кольца: (доля окружности, имя цвета в theme). Цвета — те же, что
# обозначают зоны активности в виджетах: зелёная / жёлтая / красная.
_ZONES = (
    (0.50, "COLOR_GREEN"),
    (0.25, "COLOR_YELLOW"),
    (0.25, "COLOR_RED"),
)


def _make_image() -> "Image.Image":
    """Значок: кольцо в цветах зон активности (50% / 25% / 25%)."""
    size, scale = 64, 4  # рисуем крупнее и уменьшаем — так края сглаживаются
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad, width = 6 * scale, 10 * scale
    bbox = [pad, pad, big - pad, big - pad]

    # PIL считает градусы от 3 часов по часовой стрелке, поэтому 12 часов = -90.
    start = -90.0
    for fraction, color_name in _ZONES:
        end = start + 360.0 * fraction
        color = _hex_to_rgb(getattr(theme, color_name)) + (255,)
        # Начинаем на полградуса раньше: иначе на стыках дуг видны щели.
        draw.arc(bbox, start - 0.5, end, fill=color, width=width)
        start = end

    return img.resize((size, size), Image.LANCZOS)


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


def create_tray(on_open, on_quit) -> TrayIcon | None:
    """Создаёт и запускает значок в трее. None, если трей недоступен.

    Причина (нет зависимости или сбой запуска) печатается в консоль вместе с
    командой установки — под тот интерпретатор, которым запущено приложение.
    """
    if pystray is None:
        print(f"[TRAY] Значок трея отключён — нет зависимости ({_IMPORT_ERROR}). "
              f"Установите: \"{sys.executable}\" -m pip install pystray Pillow")
        return None
    try:
        tray = TrayIcon(on_open=on_open, on_quit=on_quit)
        tray.start()
        return tray
    except Exception as e:
        print(f"[TRAY] Не удалось запустить значок трея: {e}")
        return None
