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
наведении: границы отрезка и доля активности от рабочего времени.

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
from modules.ui_utils import attach_tooltip
from utility import format_duration_short, format_percent
from .timeline_cells import cell_kinds, segment_color

# Геометрия полосы. Ширина подобрана под WIDGET_WIDTH за вычетом подписи
# «Таймлайн:» и отступов; ячейка ленты — пиксель, мельче полоса не покажет.
STRIP_WIDTH = 180
STRIP_HEIGHT = 14

_HOUR = 3600


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
    header = f"{_clock(timeline['start_seconds'])} — {_clock(timeline['end_seconds'])}"
    active = stats.get("active_seconds", 0)
    pct = active / full_day * 100
    return (
        f"{header}\n"
        f"{TIMELINE_TOOLTIP_ACTIVITY}: {format_duration_short(active)} "
        f"({format_percent(pct)} {TIMELINE_TOOLTIP_OF_WORK_TIME})"
    )


def _clock(seconds_from_midnight: int) -> str:
    """Секунды от полуночи → «HH:MM»; «сейчас» за полночью не бывает (обрезано сутками)."""
    minutes = int(seconds_from_midnight) // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


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

        # Подсказка читает текст через замыкание: перевешивать биндинг на
        # каждом обновлении незачем (тот же приём, что у недельной полосы).
        self._tooltip = TIMELINE_TOOLTIP_NO_DATA
        attach_tooltip(self._canvas, lambda: self._tooltip)

    # --- Публичный API (тот же, что у тела и недельной полосы) ---

    def update(self, stats: dict):
        """Перерисовывает ленту по `stats["timeline"]` и обновляет подсказку."""
        timeline = stats.get("timeline")
        cells = cell_kinds(timeline, STRIP_WIDTH) if timeline else []
        self._tooltip = tooltip_text(stats)

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

    def _draw_cells(self, cells: list[str]):
        """Соседние ячейки одного вида — одним прямоугольником: их сотни, а
        перерисовка идёт на каждом обновлении метрик."""
        c = self._canvas
        step = STRIP_WIDTH / len(cells)
        index = 0
        while index < len(cells):
            run = index
            while run + 1 < len(cells) and cells[run + 1] == cells[index]:
                run += 1
            c.create_rectangle(
                index * step, 0, (run + 1) * step, STRIP_HEIGHT,
                fill=segment_color(cells[index]), outline="",
            )
            index = run + 1
