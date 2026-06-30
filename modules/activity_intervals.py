"""
Чистое ядро вычисления активного времени из сырых интервалов.

Источник истины дня (схема отчёта v2):
- `sessions` — интервалы «сессия включена» [start, end];
- `idle`     — сырые гэпы простоя ввода [from, to] (БЕЗ вычета таймаута).

Активное время дня = суммарная длительность сессий за день
минус суммарная «неактивность». Неактивность одного гэпа — это интервал
[from + timeout, to]: таймаут это разовая «фора», сдвигающая начало гэпа.
Дальше всё сводится к пересечению интервалов, поэтому переход через полночь
обрабатывается корректно (фора применяется один раз, к настоящему `from`).

Функции работают с `datetime.datetime`/`datetime.date` и не делают I/O —
парсинг строк и хранение лежат на вызывающей стороне.
"""

import datetime

Interval = tuple[datetime.datetime, datetime.datetime]


def day_bounds(day: datetime.date) -> Interval:
    """Полуинтервал суток [00:00:00, следующая полночь)."""
    start = datetime.datetime.combine(day, datetime.time.min)
    return start, start + datetime.timedelta(days=1)


def _overlap_seconds(a_start, a_end, b_start, b_end) -> float:
    """Длительность пересечения двух интервалов в секундах (0, если не пересекаются)."""
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    return max(0.0, (end - start).total_seconds())


def inactive_interval(gap_from, gap_to, timeout: float) -> Interval | None:
    """Неактивная часть гэпа: [from + timeout, to]. None, если короче таймаута."""
    start = gap_from + datetime.timedelta(seconds=timeout)
    if gap_to <= start:
        return None
    return start, gap_to


def inactive_seconds(idle, timeout: float) -> int:
    """Суммарная неактивность по списку сырых гэпов (без привязки ко дню)."""
    total = 0.0
    for gap_from, gap_to in idle:
        iv = inactive_interval(gap_from, gap_to, timeout)
        if iv is not None:
            total += (iv[1] - iv[0]).total_seconds()
    return max(0, int(round(total)))


def compute_active_seconds(sessions, idle, timeout: float, day: datetime.date) -> int:
    """Активное время за `day`: Σ overlap(сессия, день) − Σ overlap([from+T,to], день)."""
    d0, d1 = day_bounds(day)

    active = 0.0
    for s_start, s_end in sessions:
        active += _overlap_seconds(s_start, s_end, d0, d1)

    inactive = 0.0
    for gap_from, gap_to in idle:
        iv = inactive_interval(gap_from, gap_to, timeout)
        if iv is not None:
            inactive += _overlap_seconds(iv[0], iv[1], d0, d1)

    return max(0, int(round(active - inactive)))


def day_segments(sessions, idle, timeout: float, day: datetime.date) -> list[tuple]:
    """Размеченные отрезки суток для графика: (start, end, "active"|"inactive").

    Внутри каждой сессии вырезаются неактивные части (гэпы длиннее таймаута).
    Промежутки между сессиями (экран заблокирован / сессия выключена) — это
    тоже простой, поэтому они помечаются "inactive", а не остаются пустыми.
    Всё обрезается границами суток. Отрезки идут по времени без перекрытий.
    """
    d0, d1 = day_bounds(day)

    inactive_ivs = []
    for gap_from, gap_to in idle:
        iv = inactive_interval(gap_from, gap_to, timeout)
        if iv is None:
            continue
        clip_s, clip_e = max(iv[0], d0), min(iv[1], d1)
        if clip_s < clip_e:
            inactive_ivs.append((clip_s, clip_e))
    inactive_ivs.sort()

    segments: list[tuple] = []
    prev_session_end = None  # конец предыдущей сессии (в пределах суток)
    for s_start, s_end in sorted(sessions):
        cursor = max(s_start, d0)
        end = min(s_end, d1)
        if cursor >= end:
            continue
        # Простой между сессиями: пробел до начала текущей сессии — нерабочее время.
        if prev_session_end is not None and cursor > prev_session_end:
            segments.append((prev_session_end, cursor, "inactive"))
        for iv_s, iv_e in inactive_ivs:
            if iv_e <= cursor or iv_s >= end:
                continue
            clip_s = max(iv_s, cursor)
            clip_e = min(iv_e, end)
            if clip_s > cursor:
                segments.append((cursor, clip_s, "active"))
            if clip_e > clip_s:
                segments.append((clip_s, clip_e, "inactive"))
            cursor = max(cursor, clip_e)
        if cursor < end:
            segments.append((cursor, end, "active"))
        # Перекрывающиеся сессии не должны порождать «отрицательный» пробел.
        prev_session_end = end if prev_session_end is None else max(prev_session_end, end)

    segments.sort(key=lambda seg: seg[0])
    return segments
