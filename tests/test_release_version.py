"""
Тесты расчёта следующей версии (scripts/release.py).

Проверяется единственное правило CalVer, на котором ошибается рука: номер
считается внутри месяца и сбрасывается на 1, когда месяц сменился. Работа с
git сюда не входит — она проверяется запуском скрипта, а не тестом.

Запуск: `python -m pytest tests/test_release_version.py`
или как скрипт: `python tests/test_release_version.py`.
"""

import datetime
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from release import ReleaseError, next_version  # noqa: E402


def test_same_month_increments_number():
    """Релиз в том же месяце — следующий порядковый номер."""
    assert next_version("2026.08.11", datetime.date(2026, 8, 30)) == "2026.08.12"


def test_new_month_resets_number():
    """Сменился месяц — номер сбрасывается на 1, месяц берётся сегодняшний."""
    assert next_version("2026.08.11", datetime.date(2026, 9, 5)) == "2026.09.1"


def test_skipped_months_are_normal():
    """Месяцы без релизов просто пропускаются: 2026.08.2 → 2026.10.1."""
    assert next_version("2026.08.2", datetime.date(2026, 10, 1)) == "2026.10.1"


def test_new_year_resets_number():
    """Смена года — тот же сброс, ведущий ноль месяца сохраняется."""
    assert next_version("2026.12.3", datetime.date(2027, 1, 9)) == "2027.01.1"


def test_month_keeps_leading_zero():
    """Месяц всегда двузначный — иначе версии перестанут сортироваться строками."""
    assert next_version("2026.09.9", datetime.date(2026, 9, 9)) == "2026.09.10"


def test_version_from_future_does_not_go_backwards():
    """Версия «из будущего» (сбитые часы, правка руками) продолжает свой месяц."""
    assert next_version("2026.09.4", datetime.date(2026, 8, 1)) == "2026.09.5"


def test_broken_version_is_rejected():
    """Версия не по схеме — остановка с понятной ошибкой, а не мусорный номер."""
    for broken in ("1.2.3", "2026.8.1", "2026.08", "", "dev"):
        try:
            next_version(broken, datetime.date(2026, 9, 5))
        except ReleaseError:
            continue
        raise AssertionError(f"версия «{broken}» должна была быть отвергнута")


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
