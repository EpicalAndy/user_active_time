"""
Недельная полоса активности — строка виджета из семи квадратиков.

Тот же вопрос, что и у тепловой карты («как прошли дни»), но в масштабе
недели и прямо в основном окне: одна строка, семь клеток, цвет — по проценту
активности за день, по той же шкале и тем же порогам, что и метрики в теле
(_color_for_percent). Подробности дня — в подсказке при наведении.

Живёт рядом с телом, а не внутри него, намеренно: в нерабочий день тело
сворачивается в серую плашку «Сегодня не рабочий день», а неделю в такой день
как раз хочется видеть — она про прошедшие дни, а не про сегодняшний.

Что показывать (`config.WIDGET_SHOW_WEEK_ACTIVITY`) читается при сборке —
как и остальные метрики тела, флаг применяется пересборкой после настроек.
Режим недели (`config.WIDGET_WEEK_MODE`) читается на каждом обновлении, так
что переключение календарная/скользящая применяется со следующим тиком.
"""

import datetime
import tkinter as tk

import config
from config import MAIN_FONT_SIZE
from constants import (
    FONT_FAMILY,
    METRIC_WEEK_ACTIVITY,
    WEEK_TOOLTIP_ACTIVITY,
    WEEK_TOOLTIP_DAY_OFF,
    WEEK_TOOLTIP_FUTURE,
    WEEK_TOOLTIP_NO_DATA,
    WEEK_TOOLTIP_TODAY,
    WEEK_TOOLTIP_WORK_TIME,
    WEEKDAY_SHORT_NAMES,
)
from modules import theme
from modules.ui_utils import attach_tooltip
from modules.week_activity import (
    KIND_DAY_OFF,
    KIND_FUTURE,
    KIND_NO_DATA,
    WEEK_LENGTH,
    build_week,
)
from utility import format_date_display, format_duration_short, format_percent
from .body import _color_for_percent

# Геометрия клетки. Рамка постоянной толщины и меняет только цвет: если
# включать её лишь у «сегодня», клетка становилась бы на 4px больше соседних
# и полоса дёргалась бы по ширине.
CELL_SIZE = 14
CELL_BORDER = 2
CELL_GAP = 3


class WeekStrip:
    """Строка «Неделя: ▪▪▪▪▪▪▪» под метриками виджета."""

    def __init__(self, parent: tk.Misc):
        self.frame = tk.Frame(parent, bg=theme.COLOR_DARK_BG)

        tk.Label(
            self.frame, text=f"{METRIC_WEEK_ACTIVITY}:",
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), anchor=tk.W, padx=4,
        ).pack(side=tk.LEFT, fill=tk.Y)

        cells_frame = tk.Frame(self.frame, bg=theme.COLOR_DARK_BG, padx=4)
        cells_frame.pack(side=tk.RIGHT)

        # Клетки создаются один раз и дальше только перекрашиваются: тултип
        # читает свой текст через замыкание на _tooltips, поэтому перевешивать
        # биндинги каждую минуту не нужно.
        self._tooltips: list[str] = [""] * WEEK_LENGTH
        self._cells: list[tk.Frame] = []
        for i in range(WEEK_LENGTH):
            cell = tk.Frame(
                cells_frame, width=CELL_SIZE, height=CELL_SIZE,
                bg=theme.COLOR_GRAY, highlightthickness=CELL_BORDER,
                highlightbackground=theme.COLOR_DARK_BG,
            )
            cell.pack(side=tk.LEFT, padx=(0 if i == 0 else CELL_GAP, 0))
            attach_tooltip(cell, lambda idx=i: self._tooltips[idx])
            self._cells.append(cell)

    # --- Публичный API (тот же, что у тела) ---

    def update(self, stats: dict):
        """Перекрашивает клетки и обновляет тексты подсказок.

        Прошлые дни читаются с диска на каждом обновлении, без кэша: это шесть
        небольших JSON'ов раз в WIDGET_UPDATE_INTERVAL, зато полоса сразу
        показывает правку прошедшего дня через «Добавить активность».
        """
        week = build_week(datetime.date.today(), config.WIDGET_WEEK_MODE, stats)
        for i, (cell, data) in enumerate(zip(self._cells, week)):
            cell.configure(
                bg=cell_color(data),
                highlightbackground=border_color(data),
            )
            self._tooltips[i] = tooltip_text(data)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()

    def destroy(self):
        self.frame.destroy()


# --- Вид клетки ---
# Публичные: теми же правилами красит свои клетки мини-виджет «Тепловая карта».


def cell_color(data: dict) -> str:
    """Заливка: цвет активности, серый «нет данных», приглушённый выходной."""
    kind = data["kind"]
    if kind == KIND_FUTURE:
        return theme.COLOR_DARK_BG
    if kind == KIND_DAY_OFF:
        return theme.COLOR_DARKER_BG
    if kind == KIND_NO_DATA:
        return theme.COLOR_GRAY
    percent_value = data["activity_percent"]
    if percent_value is None:  # нормы за день нет — красить не по чему
        return theme.COLOR_GRAY
    return _color_for_percent(
        percent_value,
        config.RECOMMENDED_ACTIVITY_THRESHOLD,
        config.MIN_ACTIVITY_THRESHOLD,
    )


def border_color(data: dict) -> str:
    """Рамка: выделяет сегодня, обводит клетки без заливки, иначе невидима."""
    if data["is_today"]:
        return theme.COLOR_LIGHT_FG
    if data["kind"] in (KIND_FUTURE, KIND_DAY_OFF):
        return theme.COLOR_MUTED
    return theme.COLOR_DARK_BG


def tooltip_text(data: dict) -> str:
    """Подсказка: дата и достижения дня — активность и рабочее время в %."""
    date = data["date"]
    header = f"{WEEKDAY_SHORT_NAMES[date.weekday()]}, {format_date_display(date)}"
    if data["is_today"]:
        header += f" ({WEEK_TOOLTIP_TODAY})"

    kind = data["kind"]
    if kind == KIND_FUTURE:
        return f"{header}\n{WEEK_TOOLTIP_FUTURE}"
    if kind == KIND_NO_DATA:
        return f"{header}\n{WEEK_TOOLTIP_NO_DATA}"

    lines = [header]
    if kind == KIND_DAY_OFF:
        # У выходного нет нормы, поэтому нет и процентов: показываем только
        # факт «нерабочий» и — если в этот день что-то отработано — время.
        lines.append(WEEK_TOOLTIP_DAY_OFF)
        if data["active_seconds"]:
            lines.append(f"{WEEK_TOOLTIP_ACTIVITY}: {format_duration_short(data['active_seconds'])}")
        if data["work_seconds"]:
            lines.append(f"{WEEK_TOOLTIP_WORK_TIME}: {format_duration_short(data['work_seconds'])}")
        return "\n".join(lines)

    lines.append(_value_line(WEEK_TOOLTIP_ACTIVITY, data["active_seconds"], data["activity_percent"]))
    lines.append(_value_line(WEEK_TOOLTIP_WORK_TIME, data["work_seconds"], data["work_percent"]))
    return "\n".join(lines)


def _value_line(label: str, seconds: int, percent_value: float | None) -> str:
    """Строка подсказки «Метрика: 6ч 20м (85.5%)»; без нормы — только время."""
    text = f"{label}: {format_duration_short(seconds)}"
    if percent_value is not None:
        text += f" ({format_percent(percent_value)})"
    return text
