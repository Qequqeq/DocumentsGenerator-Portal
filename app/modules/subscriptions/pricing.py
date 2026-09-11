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