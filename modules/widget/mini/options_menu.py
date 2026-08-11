"""
Контекстное меню настроек мини-виджета.

Пункты строятся по той же декларативной схеме `options` из реестра типов, по
которой диалог управления рендерит свои контролы (см. `registry`), поэтому
новому типу виджета достаточно описать настройки — меню подхватит их само.

Разделено на два слоя:
- `plan()` — что показать: группы, пункты, какие из них активны. Чистая
  функция без tk, её и проверяют тесты;
- `fill()` — как показать: раскладывает план в `tk.Menu`.

Соглашения:
- активное значение выделяется жирным — это читается быстрее, чем индикатор
  radiobutton/checkbutton, но индикатор всё равно рисуется: он привычен и
  показывает вид выбора (одно из / набор);
- одна опция ложится в меню плоско под заголовком-разделителем, несколько (или
  слишком длинный список значений) уезжают в подменю — иначе меню виджета
  превращается в простыню;
- незнакомый `kind` молча пропускается: тип с настройкой, которую в меню не
  выразить (например, ввод числа), останется настраиваемым через диалог, а его
  ПКМ-меню просто не покажет эту опцию вместо того, чтобы упасть.
"""

import tkinter as tk

from constants import FONT_FAMILY
from .registry import OPTION_CHOICE, OPTION_MULTI, options_for

# Шрифт пунктов. Задаётся явно и обычным пунктам тоже: иначе жирные поедут
# по метрике относительно системного шрифта меню.
_FONT = (FONT_FAMILY, 9)
_FONT_ACTIVE = (FONT_FAMILY, 9, "bold")

# Сколько значений опции ещё влезает в меню плоско, не считая заголовка.
_FLAT_CHOICES_LIMIT = 8


def plan(type_key: str, opts: dict) -> list[dict]:
    """Что показать в меню для типа: [{key, label, kind, items}].

    `items` — [{value, label, active}] в порядке `choices`; `active` отмечает
    текущее значение (для набора — каждое выбранное).
    """
    groups = []
    for opt in options_for(type_key):
        kind = opt.get("kind", OPTION_CHOICE)
        if kind == OPTION_MULTI:
            active = set(_multi_value(opt, opts))
        elif kind == OPTION_CHOICE:
            active = {opts.get(opt["key"], opt["default"])}
        else:
            continue  # незнакомый вид контрола — не наше дело (см. шапку)
        groups.append({
            "key": opt["key"],
            "label": opt["label"],
            "kind": kind,
            "items": [
                {"value": value, "label": label, "active": value in active}
                for value, label in opt["choices"]
            ],
        })
    return groups


def fill(menu: tk.Menu, type_key: str, opts: dict, on_change) -> list:
    """Наполняет меню пунктами настроек типа.

    `on_change(key, value)` вызывается с новым значением опции.

    Возвращает список объектов, которые обязан удержать вызывающий: tk-переменные
    пунктов и созданные подменю. Без ссылки на них сборщик мусора унесёт
    переменные, и пункты перестанут показывать своё состояние.
    """
    groups = plan(type_key, opts)
    keep: list = []
    for group in groups:
        target = menu
        # Заголовок нужен всегда: без него «Процент / Время» висят в меню
        # без объяснения, что это за выбор.
        if len(groups) > 1 or len(group["items"]) > _FLAT_CHOICES_LIMIT:
            target = tk.Menu(menu, tearoff=0)
            keep.append(target)
            menu.add_cascade(label=group["label"], menu=target, font=_FONT)
        else:
            menu.add_command(label=group["label"], state=tk.DISABLED, font=_FONT)
        if group["kind"] == OPTION_MULTI:
            _fill_multi(target, group, on_change, keep)
        else:
            _fill_choice(target, group, on_change, keep)
    return keep


def _fill_choice(menu: tk.Menu, group: dict, on_change, keep: list):
    """Выбор одного значения — радиокнопки."""
    var = tk.StringVar(value=str(_active_value(group)))
    keep.append(var)
    for item in group["items"]:
        menu.add_radiobutton(
            label=item["label"], value=item["value"], variable=var,
            font=_FONT_ACTIVE if item["active"] else _FONT,
            command=lambda k=group["key"], v=item["value"]: on_change(k, v),
        )


def _fill_multi(menu: tk.Menu, group: dict, on_change, keep: list):
    """Набор значений — галочки; наружу отдаётся список в порядке choices."""
    variables: dict[str, tk.BooleanVar] = {}
    keep.append(variables)
    for item in group["items"]:
        variables[item["value"]] = tk.BooleanVar(value=item["active"])
    for item in group["items"]:
        menu.add_checkbutton(
            label=item["label"], variable=variables[item["value"]],
            font=_FONT_ACTIVE if item["active"] else _FONT,
            command=lambda k=group["key"], g=group: on_change(
                k, [i["value"] for i in g["items"] if variables[i["value"]].get()],
            ),
        )


def _active_value(group: dict):
    """Текущее значение выбора (первый активный пункт; иначе пусто)."""
    for item in group["items"]:
        if item["active"]:
            return item["value"]
    return ""


def _multi_value(opt: dict, opts: dict) -> list:
    """Значение набора из настроек; мусор из widgets.json → дефолт."""
    value = opts.get(opt["key"], opt["default"])
    if not isinstance(value, (list, tuple)):
        return opt["default"]
    return list(value)
