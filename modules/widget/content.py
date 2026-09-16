"""
Содержимое виджета: тело с метриками и (если включена) недельная полоса.

Полоса — отдельный виджет рядом с телом, а не строка внутри него: тело в
нерабочий день прячет все метрики, а неделя нужна и в такой день. Из-за
этого тело и полоса всегда создаются, показываются, прячутся и уничтожаются
вместе — этой парой и заведует `WidgetContent`, чтобы конфигуратор не
повторял «и полосу тоже, если она есть» в каждом месте.

Набор метрик и наличие полосы читаются из config при создании — после
изменения настроек содержимое пересоздаётся целиком (см.
`ActivityWidget._rebuild_content`).
"""

import tkinter as tk

import config
from .body import WidgetBody
from .week_strip import WeekStrip


class WidgetContent:
    """Тело + недельная полоса как одно целое."""

    def __init__(self, parent: tk.Misc):
        self.body = WidgetBody(parent)
        self.week_strip = WeekStrip(parent) if config.WIDGET_SHOW_WEEK_ACTIVITY else None
        self.pack()

    def update(self, stats: dict):
        """Тело и заголовок сами решают, как реагировать на нерабочий день;
        полоса обновляется в любой день — она про прошедшие дни."""
        self.body.update(stats)
        if self.week_strip is not None:
            self.week_strip.update(stats)

    def is_working_day(self) -> bool:
        return self.body.is_working_day()

    def pack(self):
        self.body.pack(fill=tk.BOTH, expand=True)
        if self.week_strip is not None:
            self.week_strip.pack(fill=tk.X, pady=(0, 4))

    def pack_forget(self):
        self.body.pack_forget()
        if self.week_strip is not None:
            self.week_strip.pack_forget()

    def destroy(self):
        self.body.destroy()
        if self.week_strip is not None:
            self.week_strip.destroy()
            self.week_strip = None
