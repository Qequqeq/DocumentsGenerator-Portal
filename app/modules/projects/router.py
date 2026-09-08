# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.modules.auth.models import User
from app.modules.projects.dependencies import get_user_project, require_authenticated
from app.modules.projects.models import Project
from app.modules.projects.repositories import ProjectRepository
from app.shared.templating import templates

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


@router.get("/projects/{project_id}")
async def project_detail(
    request: Request,
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
):
    return templates.TemplateResponse(
        "project_detail.html",
        {
            "request": request,
            "project": project,
            "current_user_email": current_user.email,
        },
    )


@router.post("/projects/{project_id}/delete")
async def project_delete(
    current_user: User = Depends(require_authenticated),
    project: Project = Depends(get_user_project),
    db: AsyncSession = Depends(get_db),
):
    await ProjectRepository.delete(db, project.id, current_user.id)
    return RedirectResponse(url="/projects", status_code=303)