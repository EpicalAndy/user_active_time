"""
Мини-виджет «Отметки времени» — метрики-моменты списком.

Отдельный тип, а не полосы «Метрик»: там каждая строка — доля от нормы, и
длина заливки несёт смысл. Здесь метрика отвечает не «сколько», а «когда»:
значение — точка на часах (HH:MM), у которой нет процента, и рисовать её
полосой было бы неправдой. Поэтому строки без заливки: название слева,
время справа.

Цвет каждая отметка берёт из шкалы своей метрики в теле основного виджета:
«До рекомендуемой активности» — по проценту активности, «Конец дня» — по
проценту присутствия. Прочерк «—» — момента ещё нет (нерабочий день, за день не было
ни одной сессии).

Набор строк настраивается галочками (опция `marks`), порядок фиксированный —
он задан `_MARKS`, а не порядком кликов, чтобы виджет не «перетасовывался».
Высота окна зависит от числа включённых строк — как у полос, размер окна
подстраивается сам (см. `BaseMiniWidget._position`).
"""

import tkinter as tk

import config
from constants import FONT_FAMILY
from texts import (
    METRIC_RECOMMENDED_ETA,
    METRIC_WORK_DAY_END,
    WIDGET_CAPTION_TIME_MARKS,
    WIDGET_MARKS_EMPTY,
)
from modules import theme
from ..body import _color_for_percent, _work_time_percent
from .base import PERCENT_DECIMALS, BaseMiniWidget

# Геометрия. Ширина — под самое длинное название плюс «HH:MM» с отступами
# (замер шрифтом: «До рекомендуемой активности» + значение = 224px).
WIDTH = 230
ROW_HEIGHT = 18
ROW_GAP = 5
PAD_X = 10
FONT_SIZE = 9
VALUE_FONT_SIZE = 10

# Заполнитель, когда момента ещё нет.
_EMPTY_VALUE = "—"


# --- Метрики ---


def _recommended_eta(stats: dict):
    """До рекомендуемой активности: цвет — по шкале активности, как в теле виджета."""
    value = stats.get("recommended_eta")
    if not value:
        return None
    return value, _color_for_percent(
        stats.get("activity_percent", 0),
        config.RECOMMENDED_ACTIVITY_THRESHOLD, config.MIN_ACTIVITY_THRESHOLD,
        PERCENT_DECIMALS,
    )


def _work_day_end(stats: dict):
    """Конец дня: цвет — по шкале рабочего времени, как в теле виджета.

    Отметка стоит на месте весь день, а цвет к ней подтягивается: красный,
    пока присутствия мало, жёлтый с `MIN_WORK_TIME_THRESHOLD`, зелёный на
    `RECOMMENDED_WORK_TIME_THRESHOLD` — то есть когда до отметки дошли.
    """
    value = stats.get("work_day_end")
    if not value:
        return None
    percent = _work_time_percent(stats)
    if percent is None:  # нормы присутствия нет — красить не по чему
        return value, theme.COLOR_LIGHT_FG
    return value, _color_for_percent(
        percent,
        config.RECOMMENDED_WORK_TIME_THRESHOLD, config.MIN_WORK_TIME_THRESHOLD,
        PERCENT_DECIMALS,
    )


# Порядок здесь = порядок строк в виджете.
_MARKS: dict[str, dict] = {
    "recommended_eta": {"label": METRIC_RECOMMENDED_ETA, "read": _recommended_eta},
    "work_day_end": {"label": METRIC_WORK_DAY_END, "read": _work_day_end},
}

# Для реестра: варианты галочек и набор по умолчанию (все).
MARK_CHOICES = [(key, meta["label"]) for key, meta in _MARKS.items()]
DEFAULT_MARKS = list(_MARKS)


def selected_marks(opts: dict) -> list[str]:
    """Ключи включённых строк в фиксированном порядке `_MARKS`.

    Значение из настроек чистится намеренно: `widgets.json` правится руками, а
    неизвестный ключ или не-список не должны ронять виджет.
    """
    raw = opts.get("marks", DEFAULT_MARKS)
    if isinstance(raw, str):  # одиночное значение из старого конфига
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return list(DEFAULT_MARKS)
    chosen = set(raw)
    return [key for key in _MARKS if key in chosen]


class TimeMarksWidget(BaseMiniWidget):
    """Список метрик-моментов: название слева, время справа."""

    caption = WIDGET_CAPTION_TIME_MARKS

    # --- Каркас ---

    def _build(self):
        self._canvas = tk.Canvas(
            self.window, width=WIDTH, height=self._canvas_height(),
            bg=theme.COLOR_DARK_BG, highlightthickness=0,
        )
        self._canvas.pack()
        self._caption_label = tk.Label(
            self.window, text=self.caption,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_MUTED,
            font=(FONT_FAMILY, 8),
        )
        self._caption_label.pack(fill=tk.X, pady=(0, 4))

    def _canvas_height(self) -> int:
        """Высота под текущий набор строк (пустой набор — под одну строку)."""
        rows = max(1, len(selected_marks(self.opts)))
        return rows * ROW_HEIGHT + (rows + 1) * ROW_GAP

    # --- Отрисовка ---

    def update(self, stats: dict):
        keys = selected_marks(self.opts)
        working = stats.get("is_working_day", True)

        c = self._canvas
        # Набор мог смениться через настройки — подгоняем высоту, окно
        # пересчитает свой размер само.
        height = self._canvas_height()
        if int(c.cget("height")) != height:
            c.configure(height=height)
        c.delete("all")
        c.configure(bg=theme.COLOR_DARK_BG)

        if not keys:
            c.create_text(
                WIDTH / 2, height / 2, text=WIDGET_MARKS_EMPTY,
                fill=theme.COLOR_MUTED, font=(FONT_FAMILY, FONT_SIZE),
            )
            return

        y = ROW_GAP
        for key in keys:
            meta = _MARKS[key]
            reading = meta["read"](stats) if working else None
            if reading is None:
                # Нерабочий день или момента ещё нет — прочерк без цвета.
                value, color = _EMPTY_VALUE, theme.COLOR_MUTED
            else:
                value, color = reading
            self._draw_row(y, meta["label"], value, color)
            y += ROW_HEIGHT + ROW_GAP

    def _draw_row(self, y: int, label: str, value: str, color: str):
        """Одна строка: приглушённое название слева, значение цветом справа."""
        c = self._canvas
        text_y = y + ROW_HEIGHT / 2
        c.create_text(
            PAD_X, text_y, text=label, anchor=tk.W,
            fill=theme.COLOR_MUTED, font=(FONT_FAMILY, FONT_SIZE),
        )
        c.create_text(
            WIDTH - PAD_X, text_y, text=value, anchor=tk.E,
            fill=color, font=(FONT_FAMILY, VALUE_FONT_SIZE, "bold"),
        )
