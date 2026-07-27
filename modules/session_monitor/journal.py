"""
Человекочитаемый лог дня: сборка и разбор строк `log_entries`.

Чистый текстовый слой — не читает и не пишет состояние, поэтому его может
использовать кто угодно из пакета без риска циклов. Формат строки один на всё
приложение:

    YYYY-MM-DD HH:MM:SS | пользователь | СОБЫТИЕ (пояснение)

Он же — формат, который читают дневные отчёты и диалог ручного времени, поэтому
менять его нужно здесь, а не по месту вызова.
"""

from config import USERNAME
from utility import format_time, format_timestamp, parse_time

# Префиксы событий ручного времени. Пара START/END сопоставляется по описанию.
MANUAL_START = "MANUAL_ADD_START"
MANUAL_END = "MANUAL_ADD_END"


def line(timestamp: str, event: str) -> str:
    """Строка лога из готовой метки времени (когда datetime уже не под рукой)."""
    return f"{timestamp} | {USERNAME} | {event}"


def event_line(moment, event: str) -> str:
    """Строка лога события на момент `moment` (datetime)."""
    return line(format_timestamp(moment), event)


def manual_lines(start_dt, end_dt, description: str) -> tuple[str, str]:
    """Пара строк START/END для ручного диапазона активного времени."""
    return (
        event_line(start_dt, f"{MANUAL_START} ({description})"),
        event_line(end_dt, f"{MANUAL_END} ({description})"),
    )


def idle_line(gap_from, gap_to) -> str:
    """Строка лога на закрытый гэп простоя ввода."""
    return event_line(gap_from, f"IDLE (простой до {format_time(gap_to)})")


def parse_manual_entries(log_entries: list) -> list:
    """Извлекает пары MANUAL_ADD_START/END из лога.

    Возвращает список словарей с ключами start, end, description (HH:MM:SS).
    Сопоставляет каждый START с ближайшим последующим END с тем же описанием.
    """
    pending_starts = []
    pairs = []
    for entry in log_entries:
        parts = entry.split(" | ", 2)
        if len(parts) != 3:
            continue
        ts_str, _, event = parts
        if " " not in ts_str:
            continue
        time_str = ts_str.split(" ", 1)[1]
        if event.startswith(f"{MANUAL_START} (") and event.endswith(")"):
            desc = event[len(f"{MANUAL_START} ("):-1]
            pending_starts.append((time_str, desc))
        elif event.startswith(f"{MANUAL_END} (") and event.endswith(")"):
            desc = event[len(f"{MANUAL_END} ("):-1]
            for i, (s_time, s_desc) in enumerate(pending_starts):
                if s_desc == desc and s_time < time_str:
                    pairs.append({
                        "start": s_time,
                        "end": time_str,
                        "description": desc,
                    })
                    pending_starts.pop(i)
                    break
    return pairs


def manual_seconds(log_entries: list) -> int:
    """Суммарная длительность ручных интервалов из лога (MANUAL_ADD_START/END)."""
    total = 0
    for pair in parse_manual_entries(log_entries):
        try:
            start = parse_time(pair["start"])
            end = parse_time(pair["end"])
        except ValueError:
            continue
        total += max(0, int((end - start).total_seconds()))
    return total
