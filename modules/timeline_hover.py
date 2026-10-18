"""
Подсказка к отрезку таймлайна: что под курсором и как это подписать.

Общая часть для строки таймлайна в виджете (`widget.day_timeline`) и графика
дневного отчёта (`report_viewer`). Без tkinter: на вход — время под курсором
и отрезки в секундах от полуночи, на выход — отрезок и готовая строка вида
«Простой 12:40 — 13:25 (0ч 45м)».

Длительность считается по тем же минутам, что показаны на часах: иначе
«12:40 — 13:25 (0ч 44м)» читалось бы как ошибка, хотя секунды честные.
"""

from texts import (
    TIMELINE_KIND_ACTIVE,
    TIMELINE_KIND_INACTIVE,
    TIMELINE_KIND_MANUAL,
    TIMELINE_SEGMENT_ONGOING,
    TIMELINE_SEGMENT_SPAN,
)
from utility import format_duration_short

KIND_LABELS = {
    "active": TIMELINE_KIND_ACTIVE,
    "inactive": TIMELINE_KIND_INACTIVE,
    "manual": TIMELINE_KIND_MANUAL,
}

# Отрезки, между которыми меньше секунды, считаются стыкующимися: границы
# в отчёте приходят из часов-float, и после округления бывает зазор в 1с.
_JOIN_TOLERANCE = 1


def clock(seconds_from_midnight: int) -> str:
    """Секунды от полуночи → «HH:MM» (секунды отбрасываются)."""
    minutes = int(seconds_from_midnight) // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def segment_caption(
    kind: str, start: int, end: int, *, ongoing: bool = False, notes: list[str] = (),
) -> str:
    """Строка подсказки отрезка: вид, границы, длительность и описания.

    `ongoing` — отрезок ещё идёт (упирается в «сейчас»): конец не пишем.
    `notes` — описания добавленного вручную времени, попавшего в отрезок.
    """
    duration = format_duration_short((end // 60 - start // 60) * 60)
    template = TIMELINE_SEGMENT_ONGOING if ongoing else TIMELINE_SEGMENT_SPAN
    text = template.format(
        kind=KIND_LABELS.get(kind, kind),
        start=clock(start),
        end=clock(end),
        duration=duration,
    )
    if notes:
        text += f" — {'; '.join(notes)}"
    return text


def notes_within(notes: list[tuple[int, int, str]], start: int, end: int) -> list[str]:
    """Описания ручных диапазонов, пересекающих [start, end), без повторов."""
    out: list[str] = []
    for note_start, note_end, description in notes:
        if note_start < end and note_end > start and description and description not in out:
            out.append(description)
    return out


def segment_at(segments: list[tuple[int, int, str]], moment: int) -> tuple[int, int, str] | None:
    """Отрезок под моментом `moment`, как его видно на графике.

    Добавленное время рисуется поверх остального, поэтому ищется первым.
    Соседние стыкующиеся отрезки того же вида склеиваются: на графике между
    ними нет границы, и подсказка не должна её выдумывать. None — под
    курсором фон (данных нет).
    """
    for layer in (
        [s for s in segments if s[2] == "manual"],
        [s for s in segments if s[2] != "manual"],
    ):
        layer.sort()
        for index, (start, end, kind) in enumerate(layer):
            if start <= moment < end:
                return _merge_around(layer, index)
    return None


def _merge_around(layer: list[tuple[int, int, str]], index: int) -> tuple[int, int, str]:
    start, end, kind = layer[index]
    left = index
    while left > 0 and layer[left - 1][2] == kind and start - layer[left - 1][1] <= _JOIN_TOLERANCE:
        left -= 1
        start = min(start, layer[left][0])
    right = index
    while (
        right + 1 < len(layer)
        and layer[right + 1][2] == kind
        and layer[right + 1][0] - end <= _JOIN_TOLERANCE
    ):
        right += 1
        end = max(end, layer[right][1])
    return start, end, kind
