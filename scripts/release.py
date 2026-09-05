"""
Выпуск релиза: бамп версии, коммит и аннотированный тег одной командой.

Запуск из корня проекта:
    python scripts/release.py "краткое описание"
    python scripts/release.py "описание" --body "подробности под заголовком"
    python scripts/release.py "описание" --dry-run        # показать план, ничего не делать
    python scripts/release.py "описание" --push           # сразу git push --follow-tags
    python scripts/release.py --version-only              # релиз без изменений в индексе

Что делает, останавливаясь на первой же проблеме:
    1. считает следующую версию по CalVer (см. version.py) от текущей и сегодняшней даты;
    2. переписывает `__version__` в version.py;
    3. коммитит то, что лежит в индексе, плюс version.py;
    4. ставит аннотированный тег `v<версия>`;
    5. по флагу `--push` отправляет коммит вместе с тегом.

Скрипт сам ничего не добавляет в индекс, кроме version.py: что войдёт в релиз,
решает `git add` до запуска. Так релизный коммит не утащит случайный файл,
который валялся рядом в рабочем дереве.

Тег — половина смысла этого скрипта. Из первых одиннадцати релизов проекта
пять (08.6–08.10) остались без тегов: руками проседает именно этот шаг, а не
номер версии.

Живёт в scripts/, а не в version.py, намеренно: version.py импортируется
приложением и уезжает в сборку PyInstaller, где нет ни репозитория, ни git.
Там он остаётся источником истины про версию — строкой, которую читают.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VERSION_FILE = os.path.join(_PROJECT_ROOT, "version.py")
_ENCODING = "utf-8"

# Присваивание версии в version.py и её формат ГОД.МЕСЯЦ.НОМЕР.
# Пробелы вокруг «=» — именно [ \t], а не \s: \s включает перевод строки, и
# в MULTILINE хвостовой `\s*$` сожрал бы пустые строки за присваиванием.
_ASSIGN_RE = re.compile(r'^__version__[ \t]*=[ \t]*"([^"]*)"[ \t]*$', re.MULTILINE)
_VERSION_RE = re.compile(r"^\d{4}\.\d{2}\.\d+$")


class ReleaseError(Exception):
    """Ожидаемая остановка: печатается сообщением, без стектрейса."""


# --- Версия ---


def next_version(current: str, today: datetime.date) -> str:
    """Следующая версия по CalVer: тот же месяц — номер +1, новый месяц — сброс на 1.

    Если текущая версия «из будущего» (сбились часы, версию правили руками),
    продолжаем её месяц, а не откатываемся назад: версии обязаны расти.
    """
    if not _VERSION_RE.match(current):
        raise ReleaseError(
            f"версия «{current}» не похожа на CalVer ГОД.МЕСЯЦ.НОМЕР (например 2026.08.11)",
        )
    year, month, build = (int(part) for part in current.split("."))
    if (year, month) >= (today.year, today.month):
        return f"{year}.{month:02d}.{build + 1}"
    return f"{today.year}.{today.month:02d}.1"


def read_version() -> str:
    """Текущая версия из version.py.

    Читается регуляркой, а не импортом: скрипту нужен только текст файла, и
    тянуть ради этого модуль приложения (а с ним и его импорты) незачем.
    """
    match = _ASSIGN_RE.search(_read_file())
    if match is None:
        raise ReleaseError(f'в {_VERSION_FILE} не нашлось строки вида __version__ = "..."')
    return match.group(1)


def _read_file() -> str:
    with open(_VERSION_FILE, "r", encoding=_ENCODING) as f:
        return f.read()


def _write_version(version: str):
    text = _ASSIGN_RE.sub(f'__version__ = "{version}"', _read_file(), count=1)
    with open(_VERSION_FILE, "w", encoding=_ENCODING) as f:
        f.write(text)


# --- Git ---


def _git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=_PROJECT_ROOT,
        capture_output=True, text=True, encoding=_ENCODING,
    )
    if check and result.returncode != 0:
        # Молчаливое падение (например, пре-коммит хук без вывода) тоже должно
        # быть читаемым сообщением, а не пустой строкой после двоеточия.
        output = (result.stderr or result.stdout).strip() or f"код возврата {result.returncode}"
        raise ReleaseError(f"`git {' '.join(args)}` не выполнилась:\n{output}")
    return result.stdout.strip()


def _staged_files() -> list[str]:
    return [line for line in _git("diff", "--cached", "--name-only").splitlines() if line]


def _check_ready(tag: str, version_only: bool):
    """Проверки до первой записи: дальше откатывать дороже, чем не начинать.

    Сверяется именно строка версии, а не весь version.py: правка докстринга
    в этом файле — обычное изменение, которому место в релизном коммите, и
    блокировать из-за неё релиз незачем.
    """
    _git("rev-parse", "--git-dir")

    committed = _ASSIGN_RE.search(_git("show", "HEAD:version.py"))
    if committed is not None and committed.group(1) != read_version():
        raise ReleaseError(
            f"версия уже правлена руками: в HEAD {committed.group(1)}, "
            f"в рабочем дереве {read_version()}.\n"
            "Иначе вышел бы двойной инкремент. Сбрось правку версии "
            "(git checkout -- version.py) и запусти скрипт заново.",
        )
    if _git("tag", "--list", tag):
        raise ReleaseError(f"тег {tag} уже существует — версия {tag[1:]} уже выпускалась")
    if not _staged_files() and not version_only:
        raise ReleaseError(
            "в индексе пусто — нечего выпускать.\n"
            "Добавь изменения (git add ...) или запусти с --version-only, "
            "если релиз состоит из одного бампа версии.",
        )


def _rollback(previous: str, was_staged: bool):
    """Возвращает version.py в исходное состояние после неудачного коммита.

    Из индекса файл убирается, только если его туда положил скрипт: правку
    version.py могли застейджить и намеренно (например, докстринг), и рушить
    чужой индекс из-за своей неудачи нечестно.
    """
    _write_version(previous)
    if not was_staged:
        _git("reset", "--quiet", "HEAD", "--", "version.py", check=False)


# --- Сценарий ---


def _release(args) -> int:
    current = read_version()
    version = next_version(current, datetime.date.today())
    tag = f"v{version}"

    _check_ready(tag, args.version_only)

    subject = f"Release {version}"
    if args.description:
        subject += f": {args.description}"
    staged = _staged_files()

    print(f"[RELEASE] версия  {current} -> {version}")
    print(f"[RELEASE] коммит  {subject}")
    print(f"[RELEASE] файлы   version.py + в индексе: {len(staged)}")
    for path in staged:
        print(f"[RELEASE]           {path}")
    print(f"[RELEASE] тег     {tag} (аннотированный)")
    print(f"[RELEASE] пуш     {'git push --follow-tags' if args.push else 'нет (--push выключен)'}")

    if args.dry_run:
        print("[RELEASE] --dry-run: ничего не изменено")
        return 0

    _write_version(version)
    try:
        _git("add", "--", "version.py")
        commit_args = ["commit", "-m", subject]
        if args.body:
            commit_args += ["-m", args.body]
        _git(*commit_args)
    except ReleaseError:
        _rollback(current, was_staged="version.py" in staged)
        raise

    try:
        _git("tag", "-a", tag, "-m", f"Release {version}")
    except ReleaseError as e:
        # Коммит уже в истории — откатывать его скрипт не станет, это решение
        # автора. Даём готовую команду, чтобы дотегать вручную.
        raise ReleaseError(
            f"{e}\n\nКоммит создан, но тег не поставлен. Поставь вручную:\n"
            f'    git tag -a {tag} -m "Release {version}"',
        )

    if args.push:
        _git("push", "--follow-tags")

    print(f"[RELEASE] готово: {_git('log', '-1', '--oneline')}")
    if not args.push:
        print("[RELEASE] не забудь отправить: git push --follow-tags")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Бамп версии, релизный коммит и аннотированный тег.",
    )
    parser.add_argument(
        "description", nargs="?",
        help="краткое описание релиза — идёт в заголовок коммита после версии",
    )
    parser.add_argument("--body", help="тело коммита: подробности под заголовком")
    parser.add_argument(
        "--version-only", action="store_true",
        help="выпустить релиз с пустым индексом: в коммите будет только бамп версии",
    )
    parser.add_argument(
        "--push", action="store_true",
        help="после тега выполнить git push --follow-tags",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="показать план и выйти, ничего не изменив",
    )
    args = parser.parse_args(argv)
    try:
        return _release(args)
    except ReleaseError as e:
        print(f"[RELEASE] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
