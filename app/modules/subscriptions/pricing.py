# -*- coding: utf-8 -*-
REPORT_BASE_PRICE = 1000
REPORT_INCLUDED_WORKERS = 5
REPORT_EXTRA_WORKER_PRICE = 50


def calc_report_price(workers_count: int) -> dict:
    extra_workers = max(0, workers_count - REPORT_INCLUDED_WORKERS)
    extra_price = extra_workers * REPORT_EXTRA_WORKER_PRICE
    return {
        "base_price": REPORT_BASE_PRICE,
        "included_workers": REPORT_INCLUDED_WORKERS,
        "extra_workers": extra_workers,
        "extra_price": extra_price,
        "total": REPORT_BASE_PRICE + extra_price,
    }

# ---------- Подписки и промокоды ----------

SUBSCRIPTION_PRICES = {
    "monthly": 5000,
    "yearly": 50000,
}

PROMO_CODES = {
    "START50": {"type": "percent", "value": 50, "label": "скидка 50% для первых пользователей"},
    "WELCOME1000": {"type": "fixed", "value": 1000, "label": "скидка 1000 ₽ для новых пользователей"},
    "NIKOLAI": {"type": "percent", "value": 100, "label": "скидка 100% на подписку"}
}


def get_promo(code: str):
    if not code:
        return None
    return PROMO_CODES.get(code.strip().upper())


def price_with_promo(price: int, promo) -> tuple:
    if promo is None:
        return price, 0
    if promo["type"] == "percent":
        discount = price * promo["value"] // 100
    else:
        discount = min(price, promo["value"])
    return price - discount, discount