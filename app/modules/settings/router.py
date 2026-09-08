# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.dependencies import require_authenticated
from app.modules.auth.models import User
from app.modules.settings.risk_catalog import DANGER_DATABASE
from app.modules.settings.service import CustomizationService
from app.modules.subscriptions.dependencies import get_optional_subscription, require_subscription
from app.modules.subscriptions.models import Subscription
from app.shared.templating import templates

router = APIRouter()

@router.get("/settings")
async def settings_hub(
    request: Request,
    current_user: User = Depends(require_authenticated),
    subscription: Subscription | None = Depends(get_optional_subscription),
):
    return templates.TemplateResponse(
        "settings_hub.html",
        {"request": request, "subscription": subscription, "current_user_email": current_user.email},
    )

@router.get("/settings/descriptions")
async def settings_descriptions(
    request: Request,
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
    saved: str = "",
):
    effective = await CustomizationService.get_effective(db, current_user.id)
    return templates.TemplateResponse(
        "settings_descriptions.html",
        {
            "request": request,
            "degree_info": effective["DEGREE_INFO"],
            "chance_info": effective["CHANCE_INFO"],
            "coeff_info": effective["COEFF_INFO"],
            "control_info": effective["CONTROL_INFO"],
            "saved": saved == "1",
            "current_user_email": current_user.email,
        },
    )


@router.post("/settings/descriptions")
async def settings_descriptions_save(
    request: Request,
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    degree, chance, coeff = {}, {}, {}
    control_keys, control_values = {}, {}

    for key, raw in form.items():
        value = (raw or "").strip()
        if key.startswith("degree_"):
            degree[int(key[len("degree_"):])] = value
        elif key.startswith("chance_"):
            chance[int(key[len("chance_"):])] = value
        elif key.startswith("coeff_"):
            coeff[float(key[len("coeff_"):].replace(",", "."))] = value
        elif key.startswith("control_key_"):
            control_keys[key[len("control_key_"):]] = value
        elif key.startswith("control_value_"):
            control_values[key[len("control_value_"):]] = value

    control = {control_keys[i]: control_values.get(i, "") for i in control_keys}

    for section, values in (
        ("DEGREE_INFO", degree),
        ("CHANCE_INFO", chance),
        ("COEFF_INFO", coeff),
        ("CONTROL_INFO", control),
    ):
        if values:
            await CustomizationService.save_section(db, current_user.id, section, values)

    return RedirectResponse(url="/settings/descriptions?saved=1", status_code=303)


@router.post("/settings/reset-descriptions")
async def settings_reset_descriptions(
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
):
    for section in ("DEGREE_INFO", "CHANCE_INFO", "COEFF_INFO", "CONTROL_INFO"):
        await CustomizationService.reset_section(db, current_user.id, section)
    return RedirectResponse(url="/settings/descriptions", status_code=303)

@router.get("/settings/ranges")
async def settings_ranges(
    request: Request,
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
    saved: str = "",
    error: str = "",
):
    effective = await CustomizationService.get_effective(db, current_user.id)
    return templates.TemplateResponse(
        "settings_ranges.html",
        {
            "request": request,
            "summary_info": effective["SUMMARY_INFO"],
            "summary_info_aplication": effective["SUMMARY_INFO_APLICATION"],
            "saved": saved == "1",
            "error": error,
            "current_user_email": current_user.email,
        },
    )


@router.post("/settings/ranges")
async def settings_ranges_save(
    request: Request,
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    s_thr, s_lvl, a_thr, a_lvl = {}, {}, {}, {}

    for key, raw in form.items():
        value = (raw or "").strip()
        if key.startswith("summary_threshold_"):
            s_thr[key[len("summary_threshold_"):]] = value
        elif key.startswith("summary_level_"):
            s_lvl[key[len("summary_level_"):]] = value
        elif key.startswith("aplication_threshold_"):
            a_thr[key[len("aplication_threshold_"):]] = value
        elif key.startswith("aplication_level_"):
            a_lvl[key[len("aplication_level_"):]] = value

    try:
        summary = {float(s_thr[i].replace(",", ".")): s_lvl.get(i, "") for i in s_thr}
        aplication = {float(a_thr[i].replace(",", ".")): a_lvl.get(i, "") for i in a_thr}
    except (ValueError, KeyError):
        return RedirectResponse(url="/settings/ranges?error=invalid_number", status_code=303)

    for d in (summary, aplication):
        keys = sorted(d.keys())
        for i in range(len(keys) - 1):
            if keys[i] >= keys[i + 1]:
                return RedirectResponse(url="/settings/ranges?error=order", status_code=303)

    await CustomizationService.save_section(db, current_user.id, "SUMMARY_INFO", summary)
    await CustomizationService.save_section(db, current_user.id, "SUMMARY_INFO_APLICATION", aplication)
    return RedirectResponse(url="/settings/ranges?saved=1", status_code=303)


@router.post("/settings/reset-ranges")
async def settings_reset_ranges(
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
):
    for section in ("SUMMARY_INFO", "SUMMARY_INFO_APLICATION"):
        await CustomizationService.reset_section(db, current_user.id, section)
    return RedirectResponse(url="/settings/ranges", status_code=303)

@router.get("/settings/risks")
async def settings_risks(
    request: Request,
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
    saved: str = "",
):
    measures = await CustomizationService.get_measures(db, current_user.id)
    dangers = []
    for danger in DANGER_DATABASE.values():
        risks = []
        for risk in danger.risks:
            risk_measures = measures.get(risk.risk_number, [])
            risks.append({
                "risk_number": risk.risk_number,
                "risk_name": risk.risk_name,
                "measures_text": "\n".join(risk_measures),
            })
        dangers.append({
            "danger_number": danger.danger_number,
            "danger_name": danger.danger_name,
            "risks": risks,
        })
    return templates.TemplateResponse(
        "settings_risks.html",
        {
            "request": request,
            "dangers": dangers,
            "saved": saved == "1",
            "current_user_email": current_user.email,
        },
    )


@router.post("/settings/risks")
async def settings_risks_save(
    request: Request,
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    measures_data = {}
    for key, raw in form.items():
        if key.startswith("measures_"):
            risk_number = key[len("measures_"):]
            lines = [line.strip() for line in (raw or "").split("\n") if line.strip()]
            measures_data[risk_number] = lines

    await CustomizationService.save_section(db, current_user.id, "MANAGEMENT_MEASURES", measures_data)
    return RedirectResponse(url="/settings/risks?saved=1", status_code=303)


@router.post("/settings/reset-risks")
async def settings_reset_risks(
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
):
    await CustomizationService.reset_section(db, current_user.id, "MANAGEMENT_MEASURES")
    return RedirectResponse(url="/settings/risks", status_code=303)