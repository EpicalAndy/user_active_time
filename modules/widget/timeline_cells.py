"""
Лента дня: нарезка таймлайна на ячейки и палитра видов отрезков.

Данные приходят готовыми в `stats["timeline"]` (см. session_monitor):
границы [первый логин, сейчас] и размеченные отрезки activity/inactive/manual.
Здесь — общая для всех рисующих сторон часть без Tk: кольцо «Таймлайн дня»
(`mini.timeline`), полоса в мини-виджете «Метрики» (`mini.bars`) и строка
таймлайна в теле виджета (`day_timeline`) режут одну и ту же ленту на ячейки
по своей мерке (дуга кольца / пиксель полосы) и красят одним палитром.

Модуль намеренно не импортирует ничего из `widget.mini`: тело виджета
(`body`) — общий предок мини-виджетов, и цепочка body → mini → body замкнулась бы.
"""

from modules import theme


def segment_color(kind: str) -> str:
    """Цвет вида отрезка ленты дня: активность, ручное время, простой.

    Полосы красят простой наравне с остальными; кольцо делает его фоном и
    поверх рисует только остальные два (см. `mini.timeline`).
    """
    if kind == "active":
        return theme.COLOR_GREEN
    if kind == "manual":
        return theme.COLOR_BLUE
    return theme.COLOR_RED


# Приоритет вида отрезка, когда в одну ячейку попало поровну разных: ручное
# время дороже активности (его добавили руками, оно не должно теряться).
_KIND_PRIORITY = {"manual": 2, "active": 1, "inactive": 0}


def cell_kinds(timeline: dict, cells: int) -> list[str]:
    """Вид ("active"/"manual"/"inactive"), занявший каждую ячейку ленты дня.

    Лента — отрезок [первый логин, сейчас], нарезанный на `cells` равных ячеек.
    Считается не сам отрезок, а его ПОКРЫТИЕ по ячейкам: отрезок мельче ячейки
    нарисовать нечем, а отбрасывать мелочь нельзя — при коротком таймауте
    отрезков много, и картинка наврала бы в пользу простоя.

    Каждая ячейка достаётся тому виду, которого в ней больше по времени; пустая
    остаётся простоем. Пустой список — дня ещё нет (нулевой span).
    """
    day_start = timeline["start_seconds"]
    span = timeline["end_seconds"] - day_start
    if span <= 0 or cells <= 0:
        return []

    buckets: list[dict[str, float]] = [{} for _ in range(cells)]
    cell_seconds = span / cells
    for seg_start, seg_end, kind in timeline["segments"]:
        start = max(seg_start - day_start, 0)
        end = min(seg_end - day_start, span)
        if end <= start:
            continue
        first = int(start / cell_seconds)
        last = min(int((end - 1e-9) / cell_seconds), cells - 1)
        for index in range(first, last + 1):
            cell_start = index * cell_seconds
            covered = min(end, cell_start + cell_seconds) - max(start, cell_start)
            if covered > 0:
                buckets[index][kind] = buckets[index].get(kind, 0.0) + covered

    return [_winner(bucket) for bucket in buckets]


def cell_runs(cells: list) -> list[tuple[int, int, object]]:
    """Соседние одинаковые ячейки, склеенные в полосы: [(первая, последняя, значение)].

    Ячеек сотни, а ленты перерисовываются на каждом обновлении метрик — рисуем
    фигуру на полосу, а не на ячейку. По тем же полосам подсказка находит
    участок под курсором: он ровно такой, каким его видно.
    """
    runs: list[tuple[int, int, object]] = []
    for index, value in enumerate(cells):
        if runs and runs[-1][2] == value:
            runs[-1] = (runs[-1][0], index, value)
        else:
            runs.append((index, index, value))
    return runs


def run_bounds(timeline: dict, cells: int, first: int, last: int) -> tuple[int, int]:
    """Границы полосы ячеек [first, last] в секундах от полуночи.

    Граница ячейки — приближение: смена вида лежит где-то внутри неё. Если
    не дальше ячейки от неё есть настоящая граница отрезка, берём её — тогда
    подсказка показывает время как в логе, а не с точностью до пикселя.
    Края ленты — её собственные границы (первый логин и «сейчас»).
    """
    day_start = timeline["start_seconds"]
    day_end = timeline["end_seconds"]
    cell_seconds = (day_end - day_start) / cells
    edges = {t for seg_start, seg_end, _ in timeline["segments"] for t in (seg_start, seg_end)}

    def snap(edge_index: int) -> int:
        approx = day_start + edge_index * cell_seconds
        near = [t for t in edges if abs(t - approx) <= cell_seconds]
        return min(near, key=lambda t: abs(t - approx)) if near else round(approx)

    start = day_start if first == 0 else snap(first)
    end = day_end if last == cells - 1 else snap(last + 1)
    return int(start), int(end)


def _winner(cell: dict[str, float]) -> str:
    """Вид, занявший в ячейке больше всего времени (при равенстве — приоритетный)."""
    if not cell:
        return "inactive"
    return max(cell, key=lambda kind: (cell[kind], _KIND_PRIORITY.get(kind, 0)))
