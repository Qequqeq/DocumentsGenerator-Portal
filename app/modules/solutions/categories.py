# -*- coding: utf-8 -*-

SOLUTION_CATEGORIES = [
    ("medicine", "Медицина и здравоохранение"),
    ("industry", "Промышленность и производство"),
    ("construction", "Строительство и монтаж"),
    ("transport", "Транспорт и логистика"),
    ("warehouse", "Склад и торговля"),
    ("office", "Офис, управление, ИТР, АУП"),
    ("food", "Общепит и пищевое производство"),
    ("agro", "Сельское и лесное хозяйство"),
    ("services", "Сфера услуг и ЖКХ"),
    ("oilgas", "Нефтегаз и энергетика"),
    ("water", "Водный транспорт и судоходство"),
]

CATEGORY_NAMES = dict(SOLUTION_CATEGORIES)


def category_name(slug: str) -> str:
    return CATEGORY_NAMES.get(slug, slug) if slug else "Без категории"