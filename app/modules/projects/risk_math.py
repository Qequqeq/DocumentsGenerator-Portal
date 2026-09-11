# -*- coding: utf-8 -*-
from typing import Dict, List, Tuple

_DANGERS = None
_TOTAL_RISKS = None


def dangers_list() -> List[dict]:
    global _DANGERS
    if _DANGERS is None:
        from app.modules.settings.risk_catalog import DANGER_DATABASE
        _DANGERS = [
            {
                "danger_number": str(d.danger_number),
                "danger_name": d.danger_name,
                "risks": [
                    {"risk_number": r.risk_number, "risk_name": r.risk_name}
                    for r in d.risks
                ],
            }
            for d in DANGER_DATABASE.values()
        ]
    return _DANGERS


def total_risks_count() -> int:
    global _TOTAL_RISKS
    if _TOTAL_RISKS is None:
        _TOTAL_RISKS = sum(len(d["risks"]) for d in dangers_list())
    return _TOTAL_RISKS


def risk_value(degree: float, chance: float, coeff: float) -> float:
    if degree == 0 or chance == 0 or coeff == 0:
        return 0.0
    return degree * chance * coeff


def worker_totals(inputs: Dict) -> Tuple[float, Dict[str, float]]:
    grand = 0.0
    per_danger = {}
    for danger_number, risks in (inputs or {}).items():
        danger_sum = 0.0
        for _, vals in (risks or {}).items():
            danger_sum += risk_value(
                float(vals.get("degree", 0)),
                float(vals.get("chance", 0)),
                float(vals.get("coeff", 0)),
            )
        per_danger[danger_number] = round(danger_sum, 1)
        grand += danger_sum
    return round(grand, 1), per_danger


def is_worker_filled(inputs: Dict) -> bool:
    stored = sum(len(risks or {}) for risks in (inputs or {}).values())
    return stored >= total_risks_count()


def summary_level(total: float, summary_info: Dict) -> str:
    labels = list(summary_info.values())
    for threshold in sorted(summary_info.keys(), key=float):
        if total <= float(threshold) + 1e-9:
            return summary_info[threshold]
    return labels[-1] if labels else ""