# -*- coding: utf-8 -*-
from typing import Dict, List

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.modules.auth.models import User
from app.modules.projects.dependencies import get_user_project, require_authenticated
from app.modules.projects.models import Project
from app.modules.projects.repositories import ProjectRepository
from app.shared.templating import templates
from urllib.parse import quote

from fastapi.responses import FileResponse

from app.config import get_settings
from app.modules.projects.excel_parser import (
    parse_org_data,
    parse_people_data,
    validate_date,
    validate_org_file,
    validate_people_file,
)
from app.modules.projects.schemas import ORG_LIST_FIELDS, ORG_SCALAR_FIELDS
from app.modules.projects.risk_math import (
    dangers_list,
    is_worker_filled,
    summary_level,
    worker_totals,
)
from app.modules.settings.service import CustomizationService
import json
from fastapi.responses import Response
from app.shared.text import safe_filename, translit
from app.modules.subscriptions.dependencies import get_optional_subscription
from app.modules.subscriptions.models import Subscription
from app.modules.projects.generation import generate_project_documents
from app.modules.subscriptions.pricing import calc_report_price


router = APIRouter()



@router.get("/projects")
async def projects_list(
    request: Request,
    current_user: User = Depends(require_authenticated),
    db: AsyncSession = Depends(get_db),
):
    projects = await ProjectRepository.list_for_user(db, current_user.id)

    return templates.TemplateResponse(
        "projects_list.html",
        {
            "request": request,
            "projects": projects,
            "current_user_email": current_user.email,
        },
    )


@router.post("/projects")
async def projects_create(
    current_user: User = Depends(require_authenticated),
    db: AsyncSession = Depends(get_db),
):
    project = await ProjectRepository.create(
        db=db,
        user_id=current_user.id,
    )
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)





def _org_groups():
    groups = []
    current = ("Реквизиты организации", [])
    for key, label in ORG_SCALAR_FIELDS.items():
        if key == "auditor_pos":
            groups.append(current)
            current = ("Подписанты", [])
        current[1].append((key, label))
    groups.append(current)
    return groups


async def _workspace_context(
    request: Request,
    project: Project,
    db: AsyncSession,
    excel_errors: list | None = None,
) -> dict:
    org_data = project.org_data or {}
    effective = await CustomizationService.get_effective(db, project.user_id)
    summary_info = effective["SUMMARY_INFO"]

    worker_stats = await _worker_stats(project, db)

    return {
        "request": request,
        "project": project,
        "org_data": org_data,
        "org_groups": _org_groups(),
        "org_list_fields": ORG_LIST_FIELDS,
        "org_done": bool(org_data.get("full_name")),
        "workers_done": project.workers_count > 0,
        "people": project.people_data or [],
        "worker_stats": worker_stats,
        "excel_errors": excel_errors or [],
        "saved": request.query_params.get("saved", "") == "1",
        "error": request.query_params.get("error", ""),
        "msg": request.query_params.get("msg", ""),
        "current_user_email": None,
    }

async def _worker_stats(project: Project, db: AsyncSession) -> dict:
    effective = await CustomizationService.get_effective(db, project.user_id)
    summary_info = effective["SUMMARY_INFO"]
    stats = {}
    for w in (project.people_data or []):
        inputs = (project.risk_inputs or {}).get(str(w["ID"]), {})
        grand, _ = worker_totals(inputs)
        stats[str(w["ID"])] = {
            "total": grand,
            "level": summary_level(grand, summary_info),
            "filled": is_worker_filled(inputs),
        }
    return stats


@router.get("/projects/{project_id}")
async def project_workspace(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    ctx = await _workspace_context(request, project, db)
    ctx["current_user_email"] = current_user.email
    return templates.TemplateResponse("project_workspace.html", ctx)


@router.post("/projects/{project_id}/org")
async def project_org_save(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    org = {key: (form.get(key) or "").strip() for key in ORG_SCALAR_FIELDS}

    if not org["full_name"]:
        return RedirectResponse(url=f"/projects/{project.id}?error=org_name", status_code=303)

    poses = [v.strip() for v in form.getlist("chairmen_poses") if v.strip()]
    names = [v.strip() for v in form.getlist("chairmen_names") if v.strip()]
    org["chairmen_poses"] = poses
    org["chairmen_names"] = names

    doc_date = (form.get("doc_date") or "").strip()
    if doc_date:
        is_valid, date_error = validate_date(doc_date)
        if not is_valid:
            return RedirectResponse(
                url=f"/projects/{project.id}?error=date&msg={quote(date_error or '')}",
                status_code=303,
            )
        project.doc_date = doc_date

    project.org_data = org
    project.org_name = org["full_name"]
    await ProjectRepository.update(db, project)

    return RedirectResponse(url=f"/projects/{project.id}?saved=1&open=manual", status_code=303)


@router.post("/projects/{project_id}/delete")
async def project_delete(
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    await ProjectRepository.delete(db, project.id, current_user.id)
    return RedirectResponse(url="/projects", status_code=303)

@router.post("/projects/{project_id}/upload-excel")
async def project_upload_excel(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    people_file = form.get("people_file")
    org_file = form.get("org_file")
    doc_date = (form.get("doc_date") or "").strip()

    has_people = people_file is not None and getattr(people_file, "filename", "")
    has_org = org_file is not None and getattr(org_file, "filename", "")
    if not has_people and not has_org:
        ctx = await _workspace_context(request, project, excel_errors=["Выберите хотя бы один файл .xlsx."])
        ctx["current_user_email"] = current_user.email
        return templates.TemplateResponse("project_workspace.html", ctx, status_code=400)

    project_dir = ProjectRepository.get_project_dir(current_user.id, project.id)
    excel_errors = []

    if doc_date:
        is_valid, date_error = validate_date(doc_date)
        if is_valid:
            project.doc_date = doc_date
        else:
            excel_errors.append(date_error or "Неверный формат даты.")
    else:
        excel_errors.append("Укажите дату документа (ДД.ММ.ГГГГ).")

    if has_people:
        dest = project_dir / "people.xlsx"
        dest.write_bytes(await people_file.read())
        is_valid, people_errors, df_people = validate_people_file(dest)
        if is_valid:
            project.people_data = parse_people_data(df_people)
            project.workers_count = len(project.people_data)
        else:
            dest.unlink(missing_ok=True)
            excel_errors.extend(people_errors)

    if has_org:
        dest = project_dir / "org.xlsx"
        dest.write_bytes(await org_file.read())
        is_valid, org_errors, df_org = validate_org_file(dest)
        if is_valid:
            parsed = parse_org_data(df_org)
            org_data = dict(project.org_data or {})
            org_data.update(parsed)
            project.org_data = org_data
            if parsed.get("full_name"):
                project.org_name = parsed["full_name"]
        else:
            dest.unlink(missing_ok=True)
            excel_errors.extend(org_errors)

    if excel_errors:
        ctx = await _workspace_context(request, project, excel_errors=excel_errors)
        ctx["current_user_email"] = current_user.email
        return templates.TemplateResponse("project_workspace.html", ctx, status_code=400)

    await ProjectRepository.update(db, project)
    return RedirectResponse(url=f"/projects/{project.id}?saved=1&open=upload", status_code=303)

ORG_TEMPLATE_FILES = {
    "people_blank": ("people_card_blank.xlsx", "sheet"),
    "people_example": ("people_card_example.xlsx", "sheet"),
    "people_pdf": ("people_card_example.pdf", "pdf"),
    "org_blank": ("organization_card_blank.xlsx", "sheet"),
    "org_example": ("organization_card_example.xlsx", "sheet"),
    "org_pdf": ("organization_card_example.pdf", "pdf"),
}


@router.get("/org-templates/download/{file_key}")
async def org_templates_download(file_key: str):
    if file_key not in ORG_TEMPLATE_FILES:
        raise HTTPException(status_code=404, detail="Файл не найден")
    filename, kind = ORG_TEMPLATE_FILES[file_key]
    file_path = get_settings().org_templates_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if kind == "sheet"
        else "application/pdf"
    )
    return FileResponse(file_path, media_type=media_type, filename=filename)


@router.get("/org-templates/view/{file_key}")
async def org_templates_view(file_key: str):
    if file_key not in ORG_TEMPLATE_FILES:
        raise HTTPException(status_code=404, detail="Файл не найден")
    filename, kind = ORG_TEMPLATE_FILES[file_key]
    if kind != "pdf":
        raise HTTPException(status_code=404, detail="Файл не найден")
    file_path = get_settings().org_templates_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(file_path, media_type="application/pdf", headers={"Content-Disposition": "inline"})


def _int_field(form, key: str, default: int, errors: list, label: str) -> int:
    raw = (form.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        errors.append(f"«{label}» должно быть целым числом.")
        return default
    if value < 0:
        errors.append(f"«{label}» не может быть отрицательным.")
        return default
    return value


def _worker_from_form(form) -> tuple[dict, list]:
    errors = []
    position = (form.get("position") or "").strip()
    if not position:
        errors.append("Укажите должность.")
    division_raw = (form.get("division") or "").strip()
    division = [part.strip() for part in division_raw.split("/") if part.strip()]
    worker = {
        "ID": (form.get("ID") or "").strip(),
        "position": position,
        "division": division,
        "number_at_workplace": _int_field(form, "number_at_workplace", 1, errors, "Количество работающих"),
        "woman": _int_field(form, "woman", 0, errors, "Из них женщин"),
        "minors": _int_field(form, "minors", 0, errors, "Из них несовершеннолетних"),
        "disabled": _int_field(form, "disabled", 0, errors, "Из них инвалидов"),
        "equipment": (form.get("equipment") or "").strip(),
        "materials": (form.get("materials") or "").strip(),
    }
    return worker, errors


def _next_worker_id(people: list) -> str:
    used = {str(w.get("ID")) for w in people}
    n = 1
    while str(n) in used:
        n += 1
    return str(n)


@router.get("/projects/{project_id}/workers/new")
async def worker_new(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
):
    return templates.TemplateResponse(
        "worker_form.html",
        {
            "request": request,
            "project": project,
            "worker": {},
            "idx": None,
            "is_edit": False,
            "errors": [],
            "current_user_email": current_user.email,
        },
    )


@router.post("/projects/{project_id}/workers/new")
async def worker_create(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    worker, errors = _worker_from_form(form)
    people = list(project.people_data or [])

    if not worker["ID"]:
        worker["ID"] = _next_worker_id(people)
    elif any(str(w.get("ID")) == worker["ID"] for w in people):
        errors.append(f"Сотрудник с ID {worker['ID']} уже есть в списке.")

    if errors:
        return templates.TemplateResponse(
            "worker_form.html",
            {
                "request": request,
                "project": project,
                "worker": worker,
                "idx": None,
                "is_edit": False,
                "errors": errors,
                "current_user_email": current_user.email,
            },
            status_code=400,
        )

    people.append(worker)
    project.people_data = people
    project.workers_count = len(people)
    await ProjectRepository.update(db, project)
    return RedirectResponse(url=f"/projects/{project.id}?saved=1", status_code=303)


@router.get("/projects/{project_id}/workers/{idx}/edit")
async def worker_edit(
    request: Request,
    idx: int,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
):
    people = project.people_data or []
    if idx < 0 or idx >= len(people):
        return RedirectResponse(url=f"/projects/{project.id}", status_code=303)
    return templates.TemplateResponse(
        "worker_form.html",
        {
            "request": request,
            "project": project,
            "worker": people[idx],
            "idx": idx,
            "is_edit": True,
            "errors": [],
            "current_user_email": current_user.email,
        },
    )


@router.post("/projects/{project_id}/workers/{idx}/edit")
async def worker_update(
    request: Request,
    idx: int,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    people = list(project.people_data or [])
    if idx < 0 or idx >= len(people):
        return RedirectResponse(url=f"/projects/{project.id}", status_code=303)

    form = await request.form()
    worker, errors = _worker_from_form(form)

    if not worker["ID"]:
        worker["ID"] = people[idx].get("ID") or _next_worker_id(people)
    elif any(i != idx and str(w.get("ID")) == worker["ID"] for i, w in enumerate(people)):
        errors.append(f"Сотрудник с ID {worker['ID']} уже есть в списке.")

    if errors:
        return templates.TemplateResponse(
            "worker_form.html",
            {
                "request": request,
                "project": project,
                "worker": worker,
                "idx": idx,
                "is_edit": True,
                "errors": errors,
                "current_user_email": current_user.email,
            },
            status_code=400,
        )

    people[idx] = worker
    project.people_data = people
    project.workers_count = len(people)
    await ProjectRepository.update(db, project)
    return RedirectResponse(url=f"/projects/{project.id}?saved=1", status_code=303)


@router.post("/projects/{project_id}/workers/{idx}/delete")
async def worker_delete(
    idx: int,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    people = list(project.people_data or [])
    if 0 <= idx < len(people):
        people.pop(idx)
        project.people_data = people
        project.workers_count = len(people)
        await ProjectRepository.update(db, project)
    return RedirectResponse(url=f"/projects/{project.id}?saved=1", status_code=303)


@router.get("/projects/{project_id}/workers/{idx}/risks")
async def worker_risks_page(
    request: Request,
    idx: int,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    people = project.people_data or []
    if idx < 0 or idx >= len(people):
        return RedirectResponse(url=f"/projects/{project.id}", status_code=303)
    worker = people[idx]

    effective = await CustomizationService.get_effective(db, current_user.id)
    existing = (project.risk_inputs or {}).get(str(worker["ID"]), {})
    coeff_options = [0.0] + sorted(float(k) for k in effective["COEFF_INFO"].keys())

    return templates.TemplateResponse(
        "worker_risks.html",
        {
            "request": request,
            "project": project,
            "worker": worker,
            "idx": idx,
            "dangers": dangers_list(),
            "existing": existing,
            "degree_info": effective["DEGREE_INFO"],
            "chance_info": effective["CHANCE_INFO"],
            "coeff_info": effective["COEFF_INFO"],
            "coeff_options": coeff_options,
            "errors": [],
            "current_user_email": current_user.email,
        },
    )


@router.post("/projects/{project_id}/workers/{idx}/risks")
async def worker_risks_save(
    request: Request,
    idx: int,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    people = project.people_data or []
    if idx < 0 or idx >= len(people):
        return RedirectResponse(url=f"/projects/{project.id}", status_code=303)
    worker = people[idx]

    form = await request.form()
    effective = await CustomizationService.get_effective(db, current_user.id)
    dangers = dangers_list()

    inputs: Dict = {}
    errors: List[str] = []
    for danger in dangers:
        dn = danger["danger_number"]
        rows = {}
        for risk in danger["risks"]:
            rn = risk["risk_number"]
            degree = form.get(f"degree_{dn}_{rn}")
            chance = form.get(f"chance_{dn}_{rn}")
            coeff = form.get(f"coeff_{dn}_{rn}")
            if degree is None or chance is None or coeff is None:
                errors.append(f"Заполните все множители для риска {rn}.")
                continue
            rows[rn] = {
                "degree": int(degree),
                "chance": int(chance),
                "coeff": float(coeff),
            }
        inputs[dn] = rows

    if errors:
        coeff_options = [0.0] + sorted(float(k) for k in effective["COEFF_INFO"].keys())
        return templates.TemplateResponse(
            "worker_risks.html",
            {
                "request": request,
                "project": project,
                "worker": worker,
                "idx": idx,
                "dangers": dangers,
                "existing": inputs,
                "degree_info": effective["DEGREE_INFO"],
                "chance_info": effective["CHANCE_INFO"],
                "coeff_info": effective["COEFF_INFO"],
                "coeff_options": coeff_options,
                "errors": errors[:10],
                "current_user_email": current_user.email,
            },
            status_code=400,
        )

    risk_inputs = dict(project.risk_inputs or {})
    risk_inputs[str(worker["ID"])] = inputs
    project.risk_inputs = risk_inputs
    if project.status == "draft":
        project.status = "in_progress"
    await ProjectRepository.update(db, project)

    return RedirectResponse(url=f"/projects/{project.id}/workers", status_code=303)

def _normalize_risks(risks_raw: dict) -> dict:
    inputs = {}
    for d_key, r_dict in (risks_raw or {}).items():
        try:
            d_id = str(int(float(d_key)))
        except (ValueError, TypeError):
            d_id = str(d_key)
        rows = {}
        for r_key, vals in (r_dict or {}).items():
            if not isinstance(vals, dict):
                continue
            rows[str(r_key)] = {
                "degree": int(vals.get("degree", vals.get("deg", 1))),
                "chance": int(vals.get("chance", vals.get("ch", 1))),
                "coeff": float(vals.get("coeff", vals.get("kef", 0.0))),
            }
        inputs[d_id] = rows
    return inputs

@router.get("/projects/{project_id}/workers")
async def workers_list(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    stats = await _worker_stats(project, db)
    return templates.TemplateResponse(
        "workers_list.html",
        {
            "request": request,
            "project": project,
            "workers": project.people_data or [],
            "stats": stats,
            "error": request.query_params.get("error", ""),
            "msg": request.query_params.get("msg", ""),
            "saved": request.query_params.get("saved", "") == "1",
            "current_user_email": current_user.email,
        },
    )


@router.post("/projects/{project_id}/workers/apply-template")
async def workers_apply_template(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    indices_raw = form.getlist("worker_indices")
    tpl_file = form.get("template_file")
    people = list(project.people_data or [])

    if not indices_raw or tpl_file is None or not getattr(tpl_file, "filename", ""):
        return RedirectResponse(url=f"/projects/{project.id}/workers?error=apply_args", status_code=303)
    try:
        data = json.loads(await tpl_file.read())
        risks_raw = data.get("risks")
        if not isinstance(risks_raw, dict):
            raise ValueError("missing risks")
    except Exception:
        return RedirectResponse(url=f"/projects/{project.id}/workers?error=apply_json", status_code=303)

    inputs = _normalize_risks(risks_raw)
    risk_inputs = dict(project.risk_inputs or {})
    for idx_str in indices_raw:
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        if 0 <= idx < len(people):
            risk_inputs[str(people[idx]["ID"])] = inputs
    project.risk_inputs = risk_inputs
    if project.status == "draft":
        project.status = "in_progress"
    await ProjectRepository.update(db, project)
    return RedirectResponse(url=f"/projects/{project.id}/workers?saved=1", status_code=303)


@router.post("/projects/{project_id}/workers/{idx}/save-as-template")
async def worker_save_as_template(
    request: Request,
    idx: int,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
):
    people = project.people_data or []
    if idx < 0 or idx >= len(people):
        return RedirectResponse(url=f"/projects/{project.id}", status_code=303)
    worker = people[idx]

    form = await request.form()
    risks = {}
    for danger in dangers_list():
        dn = danger["danger_number"]
        rows = {}
        for risk in danger["risks"]:
            rn = risk["risk_number"]
            degree = form.get(f"degree_{dn}_{rn}")
            chance = form.get(f"chance_{dn}_{rn}")
            coeff = form.get(f"coeff_{dn}_{rn}")
            if degree is None or chance is None or coeff is None:
                continue
            rows[rn] = {"deg": int(degree), "ch": int(chance), "kef": float(coeff)}
        if rows:
            risks[dn] = rows

    template_data = {
        "template_name": safe_filename(translit(worker["position"])).replace(" ", "_"),
        "worker_id": worker["ID"],
        "risks": risks,
    }
    filename_string = safe_filename(translit(worker["position"]))
    filename = f"{filename_string}_template.json".replace(" ", "_")
    return Response(
        content=json.dumps(template_data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/projects/{project_id}/generate")
async def project_generate(
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
    subscription: Subscription | None = Depends(get_optional_subscription),
):
    people = project.people_data or []
    if not people:
        return RedirectResponse(url=f"/projects/{project.id}?error=no_workers", status_code=303)
    stats = await _worker_stats(project, db)
    unfilled = [w["position"] for w in people if not stats.get(str(w["ID"]), {}).get("filled")]
    if unfilled:
        return RedirectResponse(
            url=f"/projects/{project.id}/workers?error=unfilled&msg={quote(', '.join(unfilled))}",
            status_code=303,
        )

    ok, error_code, count = await generate_project_documents(
        project, db, current_user.id, subscription is not None
    )
    if not ok:
        return RedirectResponse(url=f"/projects/{project.id}/results?msg={error_code}", status_code=303)

    project.status = "completed"
    project.generated_count = count
    await ProjectRepository.update(db, project)

    if subscription is not None:
        return RedirectResponse(url=f"/projects/{project.id}/results", status_code=303)
    return RedirectResponse(url=f"/projects/{project.id}/checkout", status_code=303)


@router.get("/projects/{project_id}/download-archive")
async def project_download_archive(
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    subscription: Subscription | None = Depends(get_optional_subscription),
):
    if subscription is None and project.status != "paid":
        return RedirectResponse(url=f"/projects/{project.id}/checkout", status_code=303)

    project_dir = ProjectRepository.get_project_dir(current_user.id, project.id)
    zip_path = project_dir / "cards_archive.zip"
    if not zip_path.exists():
        return RedirectResponse(url=f"/projects/{project.id}/results?msg=gen_pending", status_code=303)
    org_name = safe_filename(translit((project.org_data or {}).get("full_name", "") or "project"))
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{org_name}.zip",
    )

@router.get("/projects/{project_id}/checkout")
async def project_checkout(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    subscription: Subscription | None = Depends(get_optional_subscription),
):
    if subscription is not None or project.status == "paid":
        return RedirectResponse(url=f"/projects/{project.id}/results", status_code=303)

    return templates.TemplateResponse(
        "checkout.html",
        {
            "request": request,
            "project": project,
            "price": calc_report_price(project.workers_count),
            "current_user_email": current_user.email,
        },
    )


@router.post("/projects/{project_id}/pay")
async def project_pay(
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    subscription: Subscription | None = Depends(get_optional_subscription),
    db: AsyncSession = Depends(get_db),
):
    """MVP-заглушка оплаты: разблокирует скачивание архива.
    Следующим шагом здесь будет создание платежа в ЮKassa,
    а статус 'paid' будет выставляться вебхуком после реальной оплаты."""
    if subscription is not None:
        return RedirectResponse(url=f"/projects/{project.id}/results", status_code=303)

    project.status = "paid"
    await ProjectRepository.update(db, project)
    return RedirectResponse(url=f"/projects/{project.id}/results?msg=paid", status_code=303)


@router.get("/projects/{project_id}/results")
async def project_results(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
    subscription: Subscription | None = Depends(get_optional_subscription),
):
    people = project.people_data or []
    stats = await _worker_stats(project, db)
    filled = [
        {"position": w["position"], "total": stats[str(w["ID"])]["total"], "level": stats[str(w["ID"])]["level"]}
        for w in people
        if stats.get(str(w["ID"]), {}).get("filled")
    ]
    is_paid = project.status == "paid"
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "project": project,
            "filled": filled,
            "total_workers": len(people),
            "all_filled": len(filled) == len(people) and len(people) > 0,
            "can_download": subscription is not None or is_paid,
            "price": calc_report_price(project.workers_count),
            "msg": request.query_params.get("msg", ""),
            "current_user_email": current_user.email,
        },
    )



@router.get("/projects/{project_id}/save-project")
async def project_save_zip(
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
):
    import io
    import zipfile

    people = project.people_data or []
    risk_inputs = project.risk_inputs or {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        written = 0
        for w in people:
            inputs = risk_inputs.get(str(w["ID"]), {})
            if not inputs:
                continue
            template_data = {
                "template_name": w["position"],
                "risks": {
                    dn: {
                        rn: {"deg": v["degree"], "ch": v["chance"], "kef": v["coeff"]}
                        for rn, v in (risks or {}).items()
                    }
                    for dn, risks in inputs.items()
                },
            }
            filename = safe_filename(translit(w["position"])) + f"{w['ID']}.json"
            zf.writestr(filename, json.dumps(template_data, ensure_ascii=False, indent=2))
            written += 1
    if written == 0:
        return RedirectResponse(url=f"/projects/{project.id}/results?msg=no_filled", status_code=303)

    org_name = safe_filename(translit((project.org_data or {}).get("full_name", "") or "project"))
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=project_{org_name}.zip"},
    )