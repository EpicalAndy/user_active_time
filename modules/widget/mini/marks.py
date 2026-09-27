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

from constants import FONT_FAMILY
from texts import WIDGET_CAPTION_TIME_MARKS, WIDGET_MARKS_EMPTY
from modules import theme
from modules.metrics import BY_KEY
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

# Порядок здесь = порядок строк в виджете. Подпись, значение и цвет — из
# каталога метрик.
_MARKS = ("recommended_eta", "work_day_end")


def read_mark(key: str, stats: dict) -> tuple[str, str] | None:
    """(время, цвет) отметки или None, пока момента нет.

    Цвет — по шкале метрики, как в теле виджета; если красить не по чему
    (нет нормы присутствия) — нейтральный.
    """
    metric = BY_KEY[key]
    value = metric.value(stats)
    if value is None:
        return None
    return value, metric.color(stats, PERCENT_DECIMALS) or theme.COLOR_LIGHT_FG


# Для реестра: варианты галочек и набор по умолчанию (все).
MARK_CHOICES = [(key, BY_KEY[key].short_label) for key in _MARKS]
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
        self._build_canvas(WIDTH, self._canvas_height())

    def _canvas_height(self) -> int:
        """Высота под текущий набор строк (пустой набор — под одну строку)."""
        rows = max(1, len(selected_marks(self.opts)))
        return rows * ROW_HEIGHT + (rows + 1) * ROW_GAP

    # --- Отрисовка ---

    def update(self, stats: dict):
        keys = selected_marks(self.opts)
        working = stats.get("is_working_day", True)

        height = self._canvas_height()
        self._fit_canvas_height(height)
        c = self._canvas
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
            reading = read_mark(key, stats) if working else None
            if reading is None:
                # Нерабочий день или момента ещё нет — прочерк без цвета.
                value, color = _EMPTY_VALUE, theme.COLOR_MUTED
            else:
                value, color = reading
            self._draw_row(y, BY_KEY[key].short_label, value, color)
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
