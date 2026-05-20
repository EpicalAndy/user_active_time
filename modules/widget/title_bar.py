"""
Заголовок виджета: название, мин/закрыть, обратный отсчёт неактивности,
дополнительные метрики (процент, остаток до конца дня, до рекомендуемой нормы).

Drag-логика тоже здесь — окно двигается «за заголовок».
"""

import tkinter as tk
from collections.abc import Callable

import config
from config import MAIN_FONT_SIZE
from constants import (
    COLOR_DARK_BG,
    COLOR_HOVER,
    COLOR_LIGHT_FG,
    COLOR_RED,
    FONT_FAMILY,
)

TITLE_BG = COLOR_DARK_BG
TITLE_FG = COLOR_LIGHT_FG
MINIMIZE_HOVER = COLOR_HOVER


def _format_hm(seconds: int) -> str:
    """Форматирует секунды в «Xч Yм» (без секунд)."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}ч {m}м"


class TitleBar:
    """Заголовок виджета. Управляет своими лейблами, countdown'ом и drag'ом.

    INPUT_ACTIVITY_TIMEOUT читается из config один раз при создании TitleBar
    (сохраняем поведение исходной реализации: появление/исчезание countdown'а
    требует перезапуска приложения). Прочие WIDGET_SHOW_TITLE_* читаются
    динамически через `rebuild_metric_labels()` — диалог настроек умеет
    дёргать его после сохранения.
    """

    def __init__(
        self,
        parent_window: tk.Toplevel,
        on_close: Callable[[], None],
        on_minimize: Callable[[], None],
        on_position_changed: Callable[[], None],
    ):
        self._window = parent_window
        self._on_close = on_close
        self._on_minimize = on_minimize
        self._on_position_changed = on_position_changed

        self._countdown_blinking = False
        self._countdown_blink_bold = False
        self._drag_x = 0
        self._drag_y = 0

        self._countdown_label: tk.Label | None = None
        self._title_percent_label: tk.Label | None = None
        self._title_remaining_label: tk.Label | None = None
        self._title_recommended_remaining_label: tk.Label | None = None

        self._build()

    def _build(self):
        self.frame = tk.Frame(self._window, bg=TITLE_BG, height=30)
        self.frame.pack(fill=tk.X)
        self.frame.pack_propagate(False)

        self._title_label = tk.Label(
            self.frame, text="Активность",
            bg=TITLE_BG, fg=TITLE_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), padx=MAIN_FONT_SIZE,
        )
        self._title_label.pack(side=tk.LEFT, fill=tk.Y)

        self._close_btn = self._make_action_button("  ✕  ", self._on_close)
        self._close_btn.pack(side=tk.RIGHT, fill=tk.Y)

        self._minimize_btn = self._make_action_button("  —  ", self._on_minimize)
        self._minimize_btn.pack(side=tk.RIGHT, fill=tk.Y)

        # Countdown-лейбл создаётся один раз — переключение
        # INPUT_ACTIVITY_TIMEOUT 0↔N требует перезапуска приложения.
        if config.INPUT_ACTIVITY_TIMEOUT > 0:
            self._countdown_label = tk.Label(
                self.frame, text="",
                bg=TITLE_BG, fg=TITLE_FG,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
            )
            self._countdown_label.pack(side=tk.LEFT, fill=tk.Y)

        self._build_metric_labels()
        self._bind_drag()

    def _make_action_button(self, text: str, command: Callable[[], None]) -> tk.Label:
        btn = tk.Label(
            self.frame, text=text,
            bg=TITLE_BG, fg=TITLE_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE), cursor="hand2",
        )
        btn.bind("<Button-1>", lambda _e: command())
        btn.bind("<Enter>", lambda _e: btn.configure(fg=MINIMIZE_HOVER))
        btn.bind("<Leave>", lambda _e: btn.configure(fg=TITLE_FG))
        return btn

    def _build_metric_labels(self):
        if config.WIDGET_SHOW_TITLE_PERCENT:
            self._title_percent_label = self._make_metric_label()
        if config.WIDGET_SHOW_TITLE_REMAINING_TIME:
            self._title_remaining_label = self._make_metric_label()
        if config.WIDGET_SHOW_TITLE_RECOMMENDED_REMAINING:
            self._title_recommended_remaining_label = self._make_metric_label()

    def _make_metric_label(self) -> tk.Label:
        label = tk.Label(
            self.frame, text="",
            bg=TITLE_BG, fg=TITLE_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        )
        label.pack(side=tk.LEFT, fill=tk.Y)
        return label

    def _bind_drag(self):
        widgets: list[tk.Widget] = [self.frame, self._title_label]
        if self._countdown_label:
            widgets.append(self._countdown_label)
        if self._title_percent_label:
            widgets.append(self._title_percent_label)
        if self._title_remaining_label:
            widgets.append(self._title_remaining_label)
        if self._title_recommended_remaining_label:
            widgets.append(self._title_recommended_remaining_label)
        for w in widgets:
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", lambda _e: self._on_position_changed())

    # --- Публичный API ---

    def update_metric_labels(self, stats: dict):
        """Обновляет тексты лейблов заголовка из stats."""
        if self._title_percent_label is not None:
            self._title_percent_label.configure(
                text=f" {stats['activity_percent']:.1f}%",
            )
        if self._title_remaining_label is not None:
            self._title_remaining_label.configure(
                text=f" {_format_hm(max(0, stats.get('remaining_work_seconds', 0)))}",
            )
        if self._title_recommended_remaining_label is not None:
            self._title_recommended_remaining_label.configure(
                text=f" {_format_hm(max(0, stats.get('recommended_remaining_seconds', 0)))}",
            )

    def clear_metric_labels(self):
        """Очищает тексты лейблов (для режима «нерабочего дня»)."""
        for label in (
            self._title_percent_label,
            self._title_remaining_label,
            self._title_recommended_remaining_label,
        ):
            if label is not None:
                label.configure(text="")

    def has_countdown(self) -> bool:
        return self._countdown_label is not None

    def update_countdown(self, remaining: int | None):
        """Применяет остаток до неактивности к countdown-лейблу.

        remaining: None — сессии нет / не отслеживается, скрываем текст.
        0 — пользователь неактивен, жирный красный без мигания.
        >0 — таймер обратного отсчёта; вблизи нуля включается мигание.
        """
        if self._countdown_label is None:
            return
        if remaining is None:
            self._countdown_label.configure(text="")
            self._countdown_blink_bold = False
            return

        minutes, secs = divmod(remaining, 60)
        text = f"{minutes:02d}:{secs:02d}"

        if remaining == 0:
            # Неактивен — жирный красный, мигание выключено.
            self._countdown_blinking = False
            self._countdown_blink_bold = False
            self._countdown_label.configure(
                text=text, fg=COLOR_RED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, "bold"),
            )
            self._title_label.configure(
                fg=COLOR_RED,
                font=(FONT_FAMILY, MAIN_FONT_SIZE, "bold"),
            )
            return

        warning_threshold = config.COUNTDOWN_WARNING_SECONDS
        if warning_threshold > 0 and remaining <= warning_threshold:
            # Приближение к неактивности — мигание управляется тикером.
            self._countdown_label.configure(text=text, fg=TITLE_FG)
            self._countdown_blinking = True
            return

        # Обычное состояние.
        self._countdown_blinking = False
        self._countdown_blink_bold = False
        self._countdown_label.configure(
            text=text, fg=TITLE_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1),
        )
        self._title_label.configure(
            fg=TITLE_FG,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
        )

    def clear_countdown(self):
        """Скрывает countdown (например, на нерабочем дне)."""
        if self._countdown_label is None:
            return
        self._countdown_label.configure(text="")
        self._countdown_blinking = False

    def tick_blink(self):
        """Один шаг анимации мигания (вызывать каждые ~500мс)."""
        if not self._countdown_blinking or self._countdown_label is None:
            return
        self._countdown_blink_bold = not self._countdown_blink_bold
        weight = "bold" if self._countdown_blink_bold else "normal"
        fg = COLOR_RED if self._countdown_blink_bold else TITLE_FG
        self._countdown_label.configure(
            font=(FONT_FAMILY, MAIN_FONT_SIZE - 1, weight), fg=fg,
        )
        self._title_label.configure(
            font=(FONT_FAMILY, MAIN_FONT_SIZE, weight), fg=fg,
        )

    def rebuild_metric_labels(self):
        """Пересоздаёт опциональные лейблы заголовка по текущему config.

        Вызывать после сохранения настроек.
        """
        for attr in (
            "_title_percent_label",
            "_title_remaining_label",
            "_title_recommended_remaining_label",
        ):
            label = getattr(self, attr)
            if label is not None:
                label.destroy()
                setattr(self, attr, None)
        self._build_metric_labels()
        # Перепривязываем drag-обработчики к новым лейблам.
        self._bind_drag()

    # --- Drag ---

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self._window.winfo_x() + event.x - self._drag_x
        y = self._window.winfo_y() + event.y - self._drag_y
        self._window.geometry(f"+{x}+{y}")
