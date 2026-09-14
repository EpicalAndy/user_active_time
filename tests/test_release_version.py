"""
Тесты расчёта следующей версии и закрытия чейнджлога (scripts/release.py).

Проверяется правило CalVer, на котором ошибается рука (номер считается внутри
месяца и сбрасывается на 1, когда месяц сменился), и перенос раздела
«Не выпущено» CHANGELOG.md под номер версии: заголовок меняется, строки
остаются, пустой раздел релиз не проходит. Работа с git сюда не входит — она
проверяется запуском скрипта, а не тестом.

Запуск: `python -m pytest tests/test_release_version.py`
или как скрипт: `python tests/test_release_version.py`.
"""

import datetime
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from release import (  # noqa: E402
    UNRELEASED_HEADING,
    ReleaseError,
    next_version,
    release_changelog,
)


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


# --- Чейнджлог ---

_CHANGELOG = (
    "# Чейнджлог\n\n"
    f"{UNRELEASED_HEADING}\n\n"
    "- Добавлена метрика «Таймлайн дня».\n"
    "- Починен тултип.\n\n"
    "## 2026.09.3 — 2026-09-11\n\n"
    "- Руководства в HTML.\n"
)


def test_unreleased_section_becomes_version_heading():
    """Заголовок раздела меняется на версию с датой, строки и соседи остаются."""
    out = release_changelog(_CHANGELOG, "2026.09.4", datetime.date(2026, 9, 14))
    assert UNRELEASED_HEADING not in out
    assert "## 2026.09.4 — 2026-09-14\n\n- Добавлена метрика «Таймлайн дня».\n- Починен тултип.\n" in out
    assert "## 2026.09.3 — 2026-09-11\n\n- Руководства в HTML.\n" in out
    assert out.startswith("# Чейнджлог\n\n")


def test_empty_unreleased_section_is_rejected():
    """Пустой раздел — остановка: релиз без описания и есть то, от чего спасает чейнджлог."""
    empty = f"# Чейнджлог\n\n{UNRELEASED_HEADING}\n\n\n## 2026.09.3 — 2026-09-11\n\n- x\n"
    try:
        release_changelog(empty, "2026.09.4", datetime.date(2026, 9, 14))
    except ReleaseError:
        return
    raise AssertionError("пустой раздел «Не выпущено» должен был быть отвергнут")


def test_empty_unreleased_section_at_end_of_file_is_rejected():
    """Раздел последний в файле и пустой — то же самое."""
    try:
        release_changelog(f"# Чейнджлог\n\n{UNRELEASED_HEADING}\n", "2026.09.4", datetime.date(2026, 9, 14))
    except ReleaseError:
        return
    raise AssertionError("пустой раздел «Не выпущено» должен был быть отвергнут")


def test_missing_unreleased_section_is_rejected():
    """Раздела нет вовсе — файл ведут не по договорённости, молча выпускать нельзя."""
    try:
        release_changelog("# Чейнджлог\n\n## 2026.09.3 — 2026-09-11\n\n- x\n", "2026.09.4", datetime.date(2026, 9, 14))
    except ReleaseError:
        return
    raise AssertionError("отсутствие раздела «Не выпущено» должно было быть отвергнуто")


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
