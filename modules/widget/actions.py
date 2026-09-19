"""
Действия меню «Отчёты» и «Помощь»: открыть окно, документ, папку, ссылку.

Каждое действие — функция от окна-родителя: ему не нужно ничего из состояния
конфигуратора, только кому быть modal-родителем и где показать сообщение.
Поэтому они живут отдельно от `ActivityWidget`, а тулбар получает их
частичными применениями к окну (см. `widget._build_chrome`).

Действия, которым нужно состояние виджета (настройки, ручное время, окно
мини-виджетов), остаются методами `ActivityWidget`.
"""

import datetime
import os
import tkinter as tk
import webbrowser
from tkinter import messagebox

from config import LOG_DIR
from constants import APP_NAME
from texts import (
    ABOUT_DESCRIPTION,
    ABOUT_TITLE,
    DEV_GUIDE_PATH,
    DOC_NOT_FOUND_TEXT,
    GITHUB_URL,
    HELP_MENU_DEV_GUIDE,
    HELP_MENU_README,
    REPORT_NO_DATA_TITLE,
    REPORT_NO_PAST_TEXT,
    REPORT_NO_TODAY_TEXT,
    USER_GUIDE_PATH,
)
from modules.changelog_viewer import ChangelogViewer
from modules.heatmap_viewer import HeatmapViewer
from modules.period_report import find_latest_past_report_date, get_report_path
from modules.period_report_dialog import PeriodReportDialog
from modules.report_viewer import ReportViewer
from modules.session_monitor import checkpoint_session
from utility import resource_path
from version import __version__


# --- Отчёты ---


def view_report(parent: tk.Misc):
    """Открывает визуализацию отчёта (с выбором файла)."""
    ReportViewer(parent)


def open_today_report(parent: tk.Misc):
    """Быстрое открытие отчёта за сегодня."""
    # Принудительный чекпойнт — чтобы файл отчёта отражал идущую сессию
    # вплоть до текущего момента, а не до последнего автосохранения.
    checkpoint_session()
    path = get_report_path(datetime.date.today())
    if not os.path.exists(path):
        messagebox.showinfo(REPORT_NO_DATA_TITLE, REPORT_NO_TODAY_TEXT, parent=parent)
        return
    ReportViewer(parent, filepath=path)


def open_last_report(parent: tk.Misc):
    """Открывает ближайший по дате прошлый дневной отчёт."""
    date = find_latest_past_report_date(datetime.date.today())
    if date is None:
        messagebox.showinfo(REPORT_NO_DATA_TITLE, REPORT_NO_PAST_TEXT, parent=parent)
        return
    ReportViewer(parent, filepath=get_report_path(date))


def open_period_report(parent: tk.Misc):
    """Открывает диалог построения отчёта за период."""
    PeriodReportDialog(parent)


def open_heatmap(parent: tk.Misc):
    """Открывает окно тепловой карты активности."""
    HeatmapViewer(parent)


def open_reports_folder():
    """Папка с отчётами — в проводнике."""
    os.startfile(LOG_DIR)


# --- Помощь ---


def open_user_guide(parent: tk.Misc):
    """Открывает руководство пользователя в браузере по умолчанию."""
    _open_doc(parent, USER_GUIDE_PATH, HELP_MENU_README)


def open_dev_guide(parent: tk.Misc):
    """Открывает техническую документацию в браузере по умолчанию."""
    _open_doc(parent, DEV_GUIDE_PATH, HELP_MENU_DEV_GUIDE)


def open_changelog(parent: tk.Misc):
    """Показывает чейнджлог приложения в отдельном окне."""
    ChangelogViewer(parent)


def _open_doc(parent: tk.Misc, relative: str, title: str):
    """Открывает HTML-документ из поставки приложения (docs/)."""
    path = resource_path(relative)
    if os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showwarning(title, DOC_NOT_FOUND_TEXT.format(path=path), parent=parent)


def open_github():
    webbrowser.open(GITHUB_URL)


def open_about(parent: tk.Misc):
    """Показывает версию приложения и ссылку на репозиторий."""
    messagebox.showinfo(
        ABOUT_TITLE,
        f"{APP_NAME}\n{ABOUT_DESCRIPTION}\n\n"
        f"Версия: {__version__}\n"
        f"{GITHUB_URL}",
        parent=parent,
    )
