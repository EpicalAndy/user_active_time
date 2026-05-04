"""
Миграция дневных TXT-отчётов в JSON.

Запуск из корня проекта:
    python scripts/migrate_reports_to_json.py
    python scripts/migrate_reports_to_json.py --delete-txt   # удалить TXT после успеха
    python scripts/migrate_reports_to_json.py --overwrite    # перезаписать существующие JSON

Идёт по LOG_DIR, ищет файлы вида `{username}_dd.mm.yyyy.txt`, парсит их
старым способом (по русским меткам, с поддержкой устаревшего формата с
секцией [Поля метрик] и без неё) и пишет соответствующие `.json`.
"""

import argparse
import datetime
import json
import os
import re
import sys

# bootstrap: подключаем пользовательский config (LOG_DIR, USERNAME).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
from bootstrap import setup_user_config  # noqa: E402

setup_user_config()

from config import LOG_DIR, USERNAME  # noqa: E402
from constants import ENCODING, REPORT_JSON_VERSION  # noqa: E402


_DURATION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*ч\s+(\d+(?:\.\d+)?)\s*м\s+(\d+(?:\.\d+)?)\s*с"
)
_FIELDS_SECTION_RE = re.compile(
    r"^\[Поля метрик\]\s*\n((?:[^\n]+\n)+?)\s*\n", re.MULTILINE,
)
_FIELD_LINE_RE = re.compile(r"^\s*(\w+)\s*=\s*(.+?)\s*$")
_TXT_FILE_RE = re.compile(rf"^{re.escape(USERNAME)}_(\d{{2}}\.\d{{2}}\.\d{{4}})\.txt$")
_LOG_HEADER_MARKER = "Лог активности:"

# Дефолтные метки до перехода на JSON.
_DEFAULT_LABELS = {
    "active_time": "Общее активное время",
    "total_work": "Общее время работы",
    "max_work": "Максимальное рабочее время",
}
_FIRST_LOGIN_LABEL = "Начало рабочего дня"
_LAST_LOGOUT_LABEL = "Конец рабочего дня"
_SESSION_COUNT_LABEL = "Количество активных сессий"


def _parse_duration(text: str | None) -> int | None:
    if not text:
        return None
    m = _DURATION_RE.search(text)
    if not m:
        return None
    h, mn, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
    return int(h * 3600 + mn * 60 + s)


def _resolve_labels(text: str) -> dict[str, str]:
    labels = dict(_DEFAULT_LABELS)
    m = _FIELDS_SECTION_RE.search(text)
    if not m:
        return labels
    for line in m.group(1).splitlines():
        pair = _FIELD_LINE_RE.match(line)
        if not pair:
            continue
        key, value = pair.group(1), pair.group(2)
        if key in labels and value:
            labels[key] = value
    return labels


def _find_value(text: str, label: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(label)}:\s*(.+)$", re.MULTILINE)
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def _normalize_optional(value: str | None) -> str | None:
    if not value or value == "—":
        return None
    return value


def _convert_txt(txt_path: str, date: datetime.date) -> dict:
    with open(txt_path, "r", encoding=ENCODING) as f:
        text = f.read()

    labels = _resolve_labels(text)

    active_seconds = _parse_duration(_find_value(text, labels["active_time"])) or 0
    total_work_seconds = _parse_duration(_find_value(text, labels["total_work"]))
    max_work_seconds = _parse_duration(_find_value(text, labels["max_work"])) or 0

    first_login = _normalize_optional(_find_value(text, _FIRST_LOGIN_LABEL))
    last_logout = _normalize_optional(_find_value(text, _LAST_LOGOUT_LABEL))

    session_raw = _find_value(text, _SESSION_COUNT_LABEL) or "0"
    try:
        session_count = int(session_raw)
    except ValueError:
        session_count = 0

    log_section = text.split(_LOG_HEADER_MARKER, 1)
    log_entries = []
    if len(log_section) >= 2:
        for line in log_section[1].splitlines():
            stripped = line.strip()
            if stripped:
                log_entries.append(stripped)

    return {
        "version": REPORT_JSON_VERSION,
        "username": USERNAME,
        "date": date.isoformat(),
        "first_login": first_login,
        "last_logout": last_logout,
        "active_seconds": active_seconds,
        "max_work_seconds": max_work_seconds,
        "total_work_seconds": total_work_seconds,
        "session_count": session_count,
        "log": log_entries,
    }


def _atomic_write_json(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding=ENCODING) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description="Миграция TXT-отчётов в JSON")
    ap.add_argument("--log-dir", default=None,
                    help="Папка с отчётами (по умолчанию — LOG_DIR из конфига)")
    ap.add_argument("--delete-txt", action="store_true",
                    help="Удалять TXT после успешной конвертации")
    ap.add_argument("--overwrite", action="store_true",
                    help="Перезаписывать уже существующие JSON")
    args = ap.parse_args()

    log_dir = args.log_dir or LOG_DIR
    if not os.path.isdir(log_dir):
        print(f"Ошибка: папка не существует: {log_dir}")
        sys.exit(1)

    print(f"Папка: {log_dir}")
    print(f"Пользователь: {USERNAME}\n")

    converted = skipped = failed = 0

    for filename in sorted(os.listdir(log_dir)):
        match = _TXT_FILE_RE.match(filename)
        if not match:
            continue

        try:
            date = datetime.datetime.strptime(match.group(1), "%d.%m.%Y").date()
        except ValueError:
            print(f"SKIP (плохая дата в имени): {filename}")
            skipped += 1
            continue

        txt_path = os.path.join(log_dir, filename)
        json_name = filename[:-4] + ".json"
        json_path = os.path.join(log_dir, json_name)

        if os.path.exists(json_path) and not args.overwrite:
            print(f"SKIP (json уже есть): {filename}")
            skipped += 1
            continue

        try:
            data = _convert_txt(txt_path, date)
            _atomic_write_json(json_path, data)
            print(f"OK:   {filename} -> {json_name}")
            converted += 1
            if args.delete_txt:
                os.remove(txt_path)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL: {filename}: {e}")
            failed += 1

    print(f"\nИтого: конвертировано {converted}, пропущено {skipped}, ошибок {failed}.")


if __name__ == "__main__":
    main()
