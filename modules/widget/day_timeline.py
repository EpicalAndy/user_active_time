"""
Таймлайн дня в теле виджета — лента [первый логин, сейчас] одной полосой.

Та же лента, что кольцо «Таймлайн дня» и полоса в мини-виджете «Метрики»,
и та же раскраска, что на графике дневного отчёта:

- зелёный — активность,
- красный — простой,
- синий  — время, добавленное вручную (поверх).

Нарезка на ячейки и палитра берутся из `timeline_cells` (`cell_kinds`,
`segment_color`): здесь только отрисовка строкой тела — подпись слева, полоса
справа. Поверх ленты, как сетка на графике отчёта, стоят отметки целых часов;
подписей часов нет — ширины на них не хватает, вместо них подсказка при
наведении. Она идёт за курсором: сверху — полоса под ним, ровно такая, какой
её видно (вид, границы, длительность; у добавленного времени — описание),
полоса подсвечивается рамкой; ниже — сводка дня: границы и доля активности
от рабочего времени.

Живёт внутри тела (в отличие от недельной полосы): лента — про сегодняшний
день, и в нерабочий день ей, как и остальным метрикам, показывать нечего.
Флаг показа (`config.WIDGET_SHOW_DAY_TIMELINE`) читается при сборке тела —
как и у остальных метрик, применяется пересборкой после настроек.
"""

import math
import tkinter as tk

from config import MAIN_FONT_SIZE
from constants import FONT_FAMILY
from texts import (
    METRIC_TIMELINE,
    TIMELINE_TOOLTIP_ACTIVITY,
    TIMELINE_TOOLTIP_NO_DATA,
    TIMELINE_TOOLTIP_OF_WORK_TIME,
)
from modules import theme
from modules.timeline_hover import clock, notes_within, segment_caption
from modules.ui_utils import attach_pointer_tooltip
from utility import format_duration_short, format_percent
from .timeline_cells import cell_kinds, cell_runs, run_bounds, segment_color

# Геометрия полосы. Ширина подобрана под WIDGET_WIDTH за вычетом подписи
# «Таймлайн:» и отступов; ячейка ленты — пиксель, мельче полоса не покажет.
STRIP_WIDTH = 180
STRIP_HEIGHT = 14

_HOUR = 3600

# Черта между строкой отрезка и сводкой дня в подсказке.
_TOOLTIP_RULE = "─" * 12


def hour_tick_positions(timeline: dict, width: int) -> list[float]:
    """X-координаты отметок целых часов строго внутри отрезка ленты.

    Границы самой ленты (x = 0 и x = width) отметками не считаются, даже если
    логин пришёлся ровно на начало часа: там и так край полосы. Пустой список —
    отрезок нулевой или короче часа без целого часа внутри.
    """
    start = timeline["start_seconds"]
    span = timeline["end_seconds"] - start
    if span <= 0 or width <= 0:
        return []
    first_hour = math.floor(start / _HOUR) + 1
    last_hour = math.ceil(timeline["end_seconds"] / _HOUR) - 1
    return [
        (hour * _HOUR - start) / span * width
        for hour in range(first_hour, last_hour + 1)
    ]


def tooltip_text(stats: dict) -> str:
    """Подсказка: границы отрезка и активность в доле от рабочего времени.

    Процент — тот же, что в центре кольца таймлайна: активность делится на
    рабочее время (не на норму), поэтому это «сколько из прошедшего дня была
    активность». Не подрезается сотней: с ручным временем честно бывает больше.
    """
    timeline = stats.get("timeline")
    full_day = stats.get("full_day_seconds", 0)
    if not timeline or full_day <= 0:
        return TIMELINE_TOOLTIP_NO_DATA
    header = f"{clock(timeline['start_seconds'])} — {clock(timeline['end_seconds'])}"
    active = stats.get("active_seconds", 0)
    pct = active / full_day * 100
    return (
        f"{header}\n"
        f"{TIMELINE_TOOLTIP_ACTIVITY}: {format_duration_short(active)} "
        f"({format_percent(pct)} {TIMELINE_TOOLTIP_OF_WORK_TIME})"
    )


class DayTimelineRow:
    """Строка «Таймлайн: ▬▬▬▬▬» среди метрик тела виджета."""

    def __init__(self, parent: tk.Misc):
        self.frame = tk.Frame(parent, bg=theme.COLOR_DARK_BG)

        tk.Label(
            self.frame, text=f"{METRIC_TIMELINE}:",
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), anchor=tk.W, padx=4,
        ).pack(side=tk.LEFT, fill=tk.Y)

        self._canvas = tk.Canvas(
            self.frame, width=STRIP_WIDTH, height=STRIP_HEIGHT,
            bg=theme.COLOR_DARK_BG, highlightthickness=0,
        )
        self._canvas.pack(side=tk.RIGHT, padx=4)

        # Подсказка спрашивает текст на каждом движении мыши — из того, что
        # нарисовано последним (перевешивать биндинг на обновлении незачем).
        self._tooltip = TIMELINE_TOOLTIP_NO_DATA
        self._timeline: dict | None = None
        self._cells: list[str] = []
        attach_pointer_tooltip(
            self._canvas, self._hover_text, on_leave=self._clear_highlight,
        )

    # --- Публичный API (тот же, что у тела и недельной полосы) ---

    def update(self, stats: dict):
        """Перерисовывает ленту по `stats["timeline"]` и обновляет подсказку."""
        timeline = stats.get("timeline")
        cells = cell_kinds(timeline, STRIP_WIDTH) if timeline else []
        self._tooltip = tooltip_text(stats)
        self._timeline = timeline
        self._cells = cells

        c = self._canvas
        c.delete("all")
        c.configure(bg=theme.COLOR_DARK_BG)
        if not cells:
            # Логина сегодня ещё не было — пустой трек, как фон графика отчёта.
            c.create_rectangle(
                0, 0, STRIP_WIDTH, STRIP_HEIGHT,
                fill=theme.COLOR_LIGHT_GRAY, outline="",
            )
            return
        self._draw_cells(cells)
        for x in hour_tick_positions(timeline, STRIP_WIDTH):
            c.create_line(x, 0, x, STRIP_HEIGHT, fill=theme.COLOR_MUTED, width=1)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()

    def destroy(self):
        self.frame.destroy()

    # --- Внутреннее ---

    def _hover_text(self, x: int, _y: int) -> str:
        """Подсказка для точки x: полоса под курсором + сводка дня.

        Заодно подсвечивает эту полосу рамкой — так видно, про что подсказка.
        Без данных — одна сводка («сессий ещё не было»).
        """
        cells = self._cells
        if not cells:
            return self._tooltip
        index = min(max(int(x / STRIP_WIDTH * len(cells)), 0), len(cells) - 1)
        first, last, kind = next(run for run in cell_runs(cells) if run[0] <= index <= run[1])
        start, end = run_bounds(self._timeline, len(cells), first, last)
        notes = (
            notes_within(self._timeline.get("manual_notes", []), start, end)
            if kind == "manual" else []
        )
        caption = segment_caption(
            kind, start, end, ongoing=last == len(cells) - 1, notes=notes,
        )
        self._highlight(first, last)
        return "\n".join((caption, _TOOLTIP_RULE, self._tooltip))

    def _highlight(self, first: int, last: int):
        step = STRIP_WIDTH / len(self._cells)
        self._clear_highlight()
        self._canvas.create_rectangle(
            first * step, 0, (last + 1) * step - 1, STRIP_HEIGHT - 1,
            outline=theme.COLOR_LIGHT_FG, width=1, tags="hover",
        )

    def _clear_highlight(self):
        self._canvas.delete("hover")

    def _draw_cells(self, cells: list[str]):
        """Соседние ячейки одного вида — одним прямоугольником: их сотни, а
        перерисовка идёт на каждом обновлении метрик."""
        c = self._canvas
        step = STRIP_WIDTH / len(cells)
        for first, last, kind in cell_runs(cells):
            c.create_rectangle(
                first * step, 0, (last + 1) * step, STRIP_HEIGHT,
                fill=segment_color(kind), outline="",
            )
