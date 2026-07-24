"""
Мини-виджет «Активность» — кольцо доли активного времени от нормы.

Заполнение = процент активности (активное время / норма), цвет — по порогам
активности. В центре: процент или активное время за день.
"""

import config
from constants import WIDGET_CAPTION_ACTIVITY
from .ring import RingWidget


class ActivityPieWidget(RingWidget):
    """Кольцо активности."""

    caption = WIDGET_CAPTION_ACTIVITY

    def _fraction(self, stats: dict) -> float | None:
        return float(stats.get("activity_percent", 0))

    def _time_seconds(self, stats: dict) -> int:
        return int(stats.get("active_seconds", 0))

    def _thresholds(self) -> tuple[float, float]:
        return (
            config.RECOMMENDED_ACTIVITY_THRESHOLD,
            config.MIN_ACTIVITY_THRESHOLD,
        )
