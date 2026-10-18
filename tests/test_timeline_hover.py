"""
Тесты подсказки к отрезку таймлайна.

Подсказка обязана описывать то, что видно на полосе: полосу целиком (а не
крошечный отрезок, затерявшийся в ячейке), с границами как в логе и
длительностью, которая сходится с показанными часами. Покрыто без окон:
подпись (`timeline_hover`), поиск отрезка на графике отчёта, полосы ячеек
и их границы на ленте виджета (`timeline_cells`).

Запуск: `python -m pytest tests/test_timeline_hover.py`
или как скрипт: `python tests/test_timeline_hover.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.timeline_hover import (  # noqa: E402
    notes_within,
    segment_at,
    segment_caption,
)
from modules.widget.timeline_cells import cell_runs, run_bounds  # noqa: E402

H = 3600
M = 60


# --- Подпись ---

def test_caption_shows_bounds_and_duration():
    assert segment_caption("inactive", 12 * H + 40 * M, 13 * H + 25 * M) == (
        "Простой 12:40 — 13:25 (0ч 45м)"
    )


def test_caption_duration_matches_shown_minutes():
    """Секунды отбрасываются и у границ, и у длительности — цифры сходятся."""
    start = 12 * H + 40 * M + 50
    end = 13 * H + 25 * M + 10   # честно 44м 20с
    assert segment_caption("active", start, end) == "Активность 12:40 — 13:25 (0ч 45м)"


def test_caption_of_ongoing_segment_has_no_end():
    assert segment_caption("inactive", 16 * H + 10 * M, 16 * H + 22 * M, ongoing=True) == (
        "Простой с 16:10 (идёт, 0ч 12м)"
    )


def test_caption_appends_manual_notes():
    text = segment_caption("manual", 14 * H, 15 * H, notes=["созвон", "ревью"])
    assert text == "Добавленное время 14:00 — 15:00 (1ч 0м) — созвон; ревью"


def test_notes_within_picks_overlapping_without_repeats():
    notes = [
        (9 * H, 10 * H, "утро"),
        (14 * H, 15 * H, "созвон"),
        (15 * H, 16 * H, "созвон"),
        (17 * H, 18 * H, ""),
    ]
    assert notes_within(notes, 14 * H + 30 * M, 18 * H) == ["созвон"]


# --- Отрезок под курсором (график отчёта) ---

SEGMENTS = [
    (9 * H, 10 * H, "active"),
    (10 * H, 11 * H, "active"),        # стык с предыдущим — одна полоса
    (11 * H + 1, 12 * H, "inactive"),  # зазор в секунду от округления часов
    (12 * H, 13 * H, "active"),
    (11 * H + 30 * M, 12 * H + 30 * M, "manual"),  # поверх
]


def test_segment_at_merges_touching_segments_of_same_kind():
    assert segment_at(SEGMENTS, 9 * H + 5 * M) == (9 * H, 11 * H, "active")


def test_segment_at_prefers_manual_layer_on_top():
    assert segment_at(SEGMENTS, 12 * H) == (11 * H + 30 * M, 12 * H + 30 * M, "manual")


def test_segment_at_does_not_merge_different_kinds():
    assert segment_at(SEGMENTS, 11 * H + 10 * M) == (11 * H + 1, 12 * H, "inactive")


def test_segment_at_returns_none_over_background():
    assert segment_at(SEGMENTS, 8 * H) is None


# --- Полосы ленты виджета ---

def test_cell_runs_glue_neighbours():
    assert cell_runs(["a", "a", "b", "a"]) == [(0, 1, "a"), (2, 2, "b"), (3, 3, "a")]
    assert cell_runs([]) == []


def _timeline(segments, start=9 * H, end=13 * H):
    return {"start_seconds": start, "end_seconds": end, "segments": segments}


def test_run_bounds_snap_to_real_segment_edges():
    """Граница ячейки — приближение; рядом есть настоящая смена вида — берём её."""
    # 4 часа на 8 ячеек: ячейка — 30 минут. Простой реально начался в 10:07.
    timeline = _timeline([(9 * H, 10 * H + 7 * M, "active"), (10 * H + 7 * M, 13 * H, "inactive")])
    assert run_bounds(timeline, 8, 2, 4) == (10 * H + 7 * M, 11 * H + 30 * M)


def test_run_bounds_use_strip_edges_at_the_ends():
    """Первая полоса начинается с первого логина, последняя — упирается в «сейчас»."""
    timeline = _timeline([(9 * H + 5 * M, 12 * H, "active")])
    assert run_bounds(timeline, 8, 0, 1) == (9 * H, 10 * H)
    assert run_bounds(timeline, 8, 6, 7) == (12 * H, 13 * H)


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
