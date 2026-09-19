"""
Окно «Что нового»: чейнджлог приложения простым текстом.

CHANGELOG.md ведётся вручную и поставляется вместе со сборкой (см. main.spec),
поэтому рендерить из него HTML, как для руководств из docs/, незачем — файл
и так читается глазами. Открывать его через `os.startfile` тоже нельзя:
расширение .md в Windows часто ни к чему не привязано. Отсюда собственное
окно — оно же даёт тему приложения и не зависит от ассоциаций.
"""

import os
import tkinter as tk
from tkinter import messagebox, ttk

from config import MAIN_FONT_SIZE
from constants import ENCODING, FONT_FAMILY
from texts import CHANGELOG_PATH, CHANGELOG_TITLE, DOC_NOT_FOUND_TEXT, HELP_MENU_CHANGELOG
from modules import theme
from modules.ui_utils import center_on_screen
from utility import resource_path


class ChangelogViewer:
    """Читает CHANGELOG.md и показывает его в окне только для чтения."""

    def __init__(self, parent: tk.Misc):
        path = resource_path(CHANGELOG_PATH)
        if not os.path.exists(path):
            messagebox.showwarning(
                HELP_MENU_CHANGELOG,
                DOC_NOT_FOUND_TEXT.format(path=path),
                parent=parent,
            )
            return

        with open(path, encoding=ENCODING) as f:
            text = f.read()

        self._show_window(parent, text)

    def _show_window(self, parent: tk.Misc, text: str):
        self.win = tk.Toplevel(parent)
        self.win.title(CHANGELOG_TITLE)
        self.win.transient(parent.winfo_toplevel())
        self.win.configure(bg=theme.COLOR_DARK_BG)
        self.win.geometry("760x560")
        self.win.minsize(420, 300)

        container = tk.Frame(self.win, bg=theme.COLOR_DARK_BG, padx=12, pady=12)
        container.pack(fill=tk.BOTH, expand=True)

        body = tk.Text(
            container,
            wrap=tk.WORD,
            bg=theme.COLOR_DARK_BG, fg=theme.COLOR_LIGHT_FG,
            insertbackground=theme.COLOR_LIGHT_FG,
            selectbackground=theme.COLOR_HOVER,
            font=(FONT_FAMILY, MAIN_FONT_SIZE),
            relief=tk.FLAT, borderwidth=0,
            padx=8, pady=6,
            spacing1=1, spacing3=3,
        )
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=body.yview)
        body.configure(yscrollcommand=scrollbar.set)
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        body.tag_configure("title", font=(FONT_FAMILY, MAIN_FONT_SIZE + 4, "bold"))
        body.tag_configure(
            "version",
            font=(FONT_FAMILY, MAIN_FONT_SIZE + 1, "bold"),
            foreground=theme.COLOR_GREEN,
            spacing1=10,
        )
        _insert_markdown(body, text)
        # Только чтение, но с возможностью выделить и скопировать: state=DISABLED
        # запрещает правку и оставляет выделение работать.
        body.configure(state=tk.DISABLED)
        body.focus_set()

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        center_on_screen(self.win)


def _insert_markdown(body: tk.Text, text: str):
    """Вставляет текст как есть, подсвечивая только заголовки markdown.

    Разметку не разбираем: чейнджлог — это список строк, из markdown в нём
    встречаются лишь «# » и «## ». Решётки убираем, остальное — как в файле.
    """
    for line in text.splitlines():
        if line.startswith("## "):
            body.insert(tk.END, line[3:] + "\n", "version")
        elif line.startswith("# "):
            body.insert(tk.END, line[2:] + "\n", "title")
        else:
            body.insert(tk.END, line + "\n")
