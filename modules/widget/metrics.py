"""
Каталог метрик: одно описание на метрику для всех мест, где она показывается.

Метрика знает свои подписи, как получить из stats значение текстом и парный
процент, по какой цветовой шкале красится и какими флагами config включается
в теле виджета. Поверхности (тело, заголовок, мини-виджеты, трей) только
выбирают метрики и раскладывают их текст по своим местам — новая метрика
добавляется одной записью здесь.

Пары «время + процент» (активное время и процент активности, рабочее время и
его процент и т.д.) — одна метрика: в теле они склеиваются в одну строку
«5ч 12м (86.6%)», а без значения показывается один процент.

Порядок `METRICS` — порядок строк в теле и галочек в настройках.

Без tkinter: только строки и цвета палитры (см. `scales`).
"""

from collections.abc import Callable
from dataclasses import dataclass

import config
from texts import (
    METRIC_ACTIVE_TIME,
    METRIC_ACTIVITY_PERCENT,
    METRIC_FREE_TIME,
    METRIC_FREE_TIME_PERCENT_FULL,
    METRIC_FULL_DAY_TIME,
    METRIC_FULL_DAY_TIME_PERCENT_FULL,
    METRIC_RECOMMENDED_ETA,
    METRIC_RECOMMENDED_ETA_FULL,
    METRIC_RECOMMENDED_REMAINING_FULL,
    METRIC_RECOMMENDED_REMAINING_PERCENT_FULL,
    METRIC_REMAINING_TIME_FULL,
    METRIC_REMAINING_TIME_PERCENT_FULL,
    METRIC_SESSION_COUNT,
    METRIC_WORK_DAY_END,
    METRIC_WORK_DAY_END_FULL,
)
from utility import (
    PERCENT_DECIMALS,
    format_duration_short,
    format_duration_signed,
    format_percent,
)
from .scales import (
    color_for_percent,
    free_time_color,
    free_time_percent,
    recommended_remaining_percent,
    remaining_time_percent,
    work_time_percent,
)

# Заполнитель, когда значения нет (нормы нет, момент ещё не наступил).
EMPTY = "—"

# Цветовые шкалы: по какой семье порогов красится метрика.
SCALE_ACTIVITY = "activity"
SCALE_WORK_TIME = "work_time"
SCALE_FREE_TIME = "free_time"


@dataclass(frozen=True)
class Metric:
    """Описание метрики. Значение и процент — функции от stats."""

    key: str
    label: str                                   # подпись значения в теле
    value: Callable[[dict], str | None]          # значение текстом; None — нет данных
    show_attr: str                               # флаг config: значение в теле
    scale: str | None = None                     # цветовая шкала (None — без цвета)
    short_label: str = ""                        # для компактных мест; пусто = label
    percent: Callable[[dict], float | None] | None = None  # парный процент
    percent_label: str = ""                      # подпись, когда показан только процент
    show_percent_attr: str = ""                  # флаг config: процент в теле

    @property
    def compact_label(self) -> str:
        return self.short_label or self.label

    def render(
        self, stats: dict, *, value: bool = True, percent: bool = False,
        decimals: int = PERCENT_DECIMALS,
    ) -> str:
        """Текст метрики: «5ч 12м», «5ч 12м (86.6%)» или один «86.6%».

        value=True — значение, к нему в скобках процент (если percent=True и
        он есть); value=False — только процент. Нет данных — EMPTY.
        """
        pct = self.percent(stats) if percent and self.percent else None
        if value:
            text = self.value(stats)
            if text is None:
                return EMPTY
            return f"{text} ({format_percent(pct, decimals)})" if pct is not None else text
        return format_percent(pct, decimals) if pct is not None else EMPTY

    def color(self, stats: dict, decimals: int = PERCENT_DECIMALS) -> str | None:
        """Цвет по шкале метрики; None — шкалы нет или считать не по чему.

        `decimals` — точность показанного процента: порог сверяется с тем же
        числом, что видит пользователь (см. scales.color_for_percent).
        """
        if self.scale == SCALE_ACTIVITY:
            return color_for_percent(
                stats.get("activity_percent", 0),
                config.RECOMMENDED_ACTIVITY_THRESHOLD, config.MIN_ACTIVITY_THRESHOLD,
                decimals,
            )
        if self.scale == SCALE_WORK_TIME:
            pct = work_time_percent(stats)
            if pct is None:
                return None
            return color_for_percent(
                pct, config.RECOMMENDED_WORK_TIME_THRESHOLD, config.MIN_WORK_TIME_THRESHOLD,
                decimals,
            )
        if self.scale == SCALE_FREE_TIME:
            return free_time_color(
                stats.get("free_remaining_seconds", 0),
                stats.get("free_budget_seconds", 0),
            )
        return None


def _duration(key: str) -> Callable[[dict], str]:
    """Значение — длительность из stats[key], отрицательное подрезается нулём."""
    return lambda stats: format_duration_short(max(0, stats.get(key, 0)))


def _clock(key: str) -> Callable[[dict], str | None]:
    """Значение — момент «HH:MM» из stats[key]; None, пока его нет."""
    return lambda stats: stats.get(key) or None


METRICS: tuple[Metric, ...] = (
    Metric(
        key="activity",
        label=METRIC_ACTIVE_TIME,
        value=_duration("active_seconds"),
        show_attr="WIDGET_SHOW_ACTIVE_TIME",
        scale=SCALE_ACTIVITY,
        short_label=METRIC_ACTIVITY_PERCENT,
        percent=lambda stats: stats.get("activity_percent"),
        percent_label=METRIC_ACTIVITY_PERCENT,
        show_percent_attr="WIDGET_SHOW_ACTIVITY_PERCENT",
    ),
    Metric(
        key="work_time",
        label=METRIC_FULL_DAY_TIME,
        value=_duration("full_day_seconds"),
        show_attr="WIDGET_SHOW_FULL_DAY_TIME",
        scale=SCALE_WORK_TIME,
        percent=work_time_percent,
        percent_label=METRIC_FULL_DAY_TIME_PERCENT_FULL,
        show_percent_attr="WIDGET_SHOW_FULL_DAY_TIME_PERCENT",
    ),
    Metric(
        key="recommended_remaining",
        label=METRIC_RECOMMENDED_REMAINING_FULL,
        value=_duration("recommended_remaining_seconds"),
        show_attr="WIDGET_SHOW_RECOMMENDED_REMAINING",
        scale=SCALE_ACTIVITY,
        percent=recommended_remaining_percent,
        percent_label=METRIC_RECOMMENDED_REMAINING_PERCENT_FULL,
        show_percent_attr="WIDGET_SHOW_RECOMMENDED_REMAINING_PERCENT",
    ),
    Metric(
        key="remaining_time",
        label=METRIC_REMAINING_TIME_FULL,
        value=_duration("remaining_work_seconds"),
        show_attr="WIDGET_SHOW_REMAINING_TIME",
        scale=SCALE_WORK_TIME,
        percent=remaining_time_percent,
        percent_label=METRIC_REMAINING_TIME_PERCENT_FULL,
        show_percent_attr="WIDGET_SHOW_REMAINING_TIME_PERCENT",
    ),
    Metric(
        key="free_time",
        label=METRIC_FREE_TIME,
        # Со знаком: перерасход показываем как «-15м», а не подрезаем нулём.
        value=lambda stats: format_duration_signed(stats.get("free_remaining_seconds", 0)),
        show_attr="WIDGET_SHOW_FREE_TIME",
        scale=SCALE_FREE_TIME,
        percent=free_time_percent,
        percent_label=METRIC_FREE_TIME_PERCENT_FULL,
        show_percent_attr="WIDGET_SHOW_FREE_TIME_PERCENT",
    ),
    Metric(
        key="session_count",
        label=METRIC_SESSION_COUNT,
        value=lambda stats: str(stats.get("session_count", 0)),
        show_attr="WIDGET_SHOW_SESSION_COUNT",
    ),
    Metric(
        key="work_day_end",
        label=METRIC_WORK_DAY_END_FULL,
        value=_clock("work_day_end"),
        show_attr="WIDGET_SHOW_WORK_DAY_END",
        # Конец дня — величина из семьи рабочего времени, поэтому и шкала его:
        # цвет говорит, насколько близко присутствие подошло к этой отметке.
        scale=SCALE_WORK_TIME,
        short_label=METRIC_WORK_DAY_END,
    ),
    Metric(
        key="recommended_eta",
        label=METRIC_RECOMMENDED_ETA_FULL,
        value=_clock("recommended_eta"),
        show_attr="WIDGET_SHOW_RECOMMENDED_ETA",
        scale=SCALE_ACTIVITY,
        short_label=METRIC_RECOMMENDED_ETA,
    ),
)

BY_KEY: dict[str, Metric] = {metric.key: metric for metric in METRICS}
