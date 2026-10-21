"""
Значок приложения в системном трее (pystray).

Значок висит всё время работы приложения. Двойной клик по нему переключает
окно конфигуратора: свёрнуто в трей — открывает, открыто — сворачивает
(одиночный клик ничего не делает); правый клик — меню «Открыть / Метрика в
подсказке / Выход».

Подсказка при наведении: название с версией и одна метрика из каталога —
одна, а не набор: Windows обрезает подсказку до 127 символов, и с несколькими
метриками было бы непонятно, почему не влезает то, что выбрано. Выбор живёт в
`tray.json` в LOG_DIR (как настройки мини-виджетов в `widgets.json`: меняется
из контекстного меню, а не из диалога настроек).

pystray работает в собственном потоке (Icon.run блокирует), поэтому колбэки
`on_open`/`on_toggle`/`on_quit` вызываются НЕ в потоке Tk — вызывающая сторона обязана
переадресовать их в главный поток (например, через `root.after(0, ...)`).

pystray и Pillow — единственные внешние зависимости приложения. Если их нет,
модуль всё равно импортируется, а `create_tray` возвращает None: приложение
работает без трея.
"""

import os
import sys
import threading

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception as e:  # noqa: BLE001 — любая поломка зависимости = без трея
    pystray = None
    _IMPORT_ERROR = e

from config import LOG_DIR
from texts import (
    METRIC_HIDE_OPTION,
    TRAY_MENU_OPEN,
    TRAY_MENU_QUIT,
    TRAY_MENU_TOOLTIP_METRIC,
    TRAY_TITLE,
    TRAY_TOOLTIP_DAY_OFF,
)
from modules import theme
from modules.json_file import read_json, write_json_atomic
from modules.metrics import BY_KEY, METRICS

_TRAY_FILE = os.path.join(LOG_DIR, "tray.json")

# Метрика подсказки по умолчанию и значение «не показывать».
DEFAULT_TOOLTIP_METRIC = "activity"
NO_METRIC = ""

# Предел текста подсказки: szTip в NOTIFYICONDATAW — 128 WCHAR с нулём в конце.
# Длиннее ctypes не обрежет, а упадёт, поэтому режем сами.
_TOOLTIP_MAX = 127


def tooltip_text(metric_key: str, stats: dict | None) -> str:
    """Текст подсказки: название с версией и строка выбранной метрики.

    stats=None (ещё не пришли) или метрика не выбрана — только название.
    """
    lines = [TRAY_TITLE]
    metric = BY_KEY.get(metric_key)
    if metric is not None and stats is not None:
        if not stats.get("is_working_day", True):
            lines.append(TRAY_TOOLTIP_DAY_OFF)
        else:
            lines.append(f"{metric.short_label}: {metric.render(stats, percent=True)}")
    return "\n".join(lines)[:_TOOLTIP_MAX]


def load_tooltip_metric() -> str:
    """Сохранённый выбор метрики; неизвестный ключ или битый файл — по умолчанию."""
    data = read_json(_TRAY_FILE)
    key = data.get("tooltip_metric") if isinstance(data, dict) else None
    if key == NO_METRIC or key in BY_KEY:
        return key
    return DEFAULT_TOOLTIP_METRIC


def save_tooltip_metric(key: str):
    """Сохраняет выбор; ошибка записи не роняет трей — выбор живёт до перезапуска."""
    try:
        write_json_atomic(_TRAY_FILE, {"tooltip_metric": key})
    except OSError:
        pass


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


# Коды мыши, которые оболочка присылает в WM_NOTIFY значка (lparam).
_WM_LBUTTONUP = 0x0202
_WM_LBUTTONDBLCLK = 0x0203


def _make_icon_class():
    """pystray.Icon, который реагирует на двойной клик, а не на одиночный.

    win32-бэкенд pystray активирует значок по WM_LBUTTONUP — то есть по
    одиночному клику, и отдельного обработчика двойного у него нет. Подменяем
    `_on_notify` (приватный, но бэкенд на Windows один): одиночный клик
    глушим, двойной отдаём в `on_double_click`, остальное (правый клик →
    меню) — как было.
    """
    class _Icon(pystray.Icon):
        def __init__(self, *args, on_double_click, **kwargs):
            self._on_double_click = on_double_click
            super().__init__(*args, **kwargs)

        def _on_notify(self, wparam, lparam):
            if lparam == _WM_LBUTTONDBLCLK:
                self._on_double_click()
            elif lparam != _WM_LBUTTONUP:
                super()._on_notify(wparam, lparam)

    return _Icon


class TrayIcon:
    """Обёртка над pystray.Icon: всегда в трее, запуск/остановка в потоке.

    Подсказку пересчитывает `update_stats` (из потока Tk, в такт раздаче
    метрик ядром) и выбор метрики в меню (из потока pystray). Оба пишут только
    ссылки — ключ и последний stats — и заново собирают текст целиком.
    """

    def __init__(self, on_open, on_toggle, on_quit):
        self._on_open = on_open
        self._on_quit = on_quit
        self._thread: threading.Thread | None = None
        self._metric_key = load_tooltip_metric()
        self._stats: dict | None = None
        # default=True — только жирный шрифт пункта в меню: двойной клик
        # по значку не «открывает», а переключает окно (on_toggle).
        self._icon = _make_icon_class()(
            "user_active_time",
            _make_image(),
            tooltip_text(self._metric_key, None),
            on_double_click=on_toggle,
            menu=pystray.Menu(
                pystray.MenuItem(TRAY_MENU_OPEN, self._open, default=True),
                pystray.MenuItem(TRAY_MENU_TOOLTIP_METRIC, self._metric_menu()),
                pystray.MenuItem(TRAY_MENU_QUIT, self._quit),
            ),
        )

    def _metric_menu(self) -> "pystray.Menu":
        """Подменю выбора метрики: радиопункты по каталогу и «Не отображать»."""
        choices = [(metric.key, metric.short_label) for metric in METRICS]
        choices.append((NO_METRIC, METRIC_HIDE_OPTION))
        return pystray.Menu(*(
            pystray.MenuItem(
                label, self._select_action(key),
                checked=self._is_selected(key), radio=True,
            )
            for key, label in choices
        ))

    # pystray проверяет число аргументов обработчика по co_argcount, поэтому
    # ключ привязываем замыканием, а не параметром по умолчанию.
    def _select_action(self, key: str):
        return lambda: self._select_metric(key)

    def _is_selected(self, key: str):
        return lambda _item: self._metric_key == key

    def _select_metric(self, key: str):
        self._metric_key = key
        save_tooltip_metric(key)
        # win32-бэкенд собирает меню один раз — отметку переставляем явно.
        self._icon.update_menu()
        self._refresh_title()

    def update_stats(self, stats: dict):
        """Свежие метрики от ядра — пересчитывает подсказку."""
        self._stats = stats
        self._refresh_title()

    def _refresh_title(self):
        text = tooltip_text(self._metric_key, self._stats)
        if self._icon.title != text:
            self._icon.title = text

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


def create_tray(on_open, on_toggle, on_quit) -> TrayIcon | None:
    """Создаёт и запускает значок в трее. None, если трей недоступен.

    Причина (нет зависимости или сбой запуска) печатается в консоль вместе с
    командой установки — под тот интерпретатор, которым запущено приложение.
    """
    if pystray is None:
        print(f"[TRAY] Значок трея отключён — нет зависимости ({_IMPORT_ERROR}). "
              f"Установите: \"{sys.executable}\" -m pip install pystray Pillow")
        return None
    try:
        tray = TrayIcon(on_open=on_open, on_toggle=on_toggle, on_quit=on_quit)
        tray.start()
        return tray
    except Exception as e:
        print(f"[TRAY] Не удалось запустить значок трея: {e}")
        return None
