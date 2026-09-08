# -*- coding: utf-8 -*-
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.projects.models import Project
from app.modules.projects.repositories import ProjectRepository
from app.shared.exceptions import RedirectException


async def require_authenticated(
    current_user: User | None = Depends(get_current_user),
) -> User:
    if current_user is None:
        raise RedirectException("/#register")
    return current_user


async def get_user_project(
    project_id: str,
    current_user: User = Depends(require_authenticated),
    db: AsyncSession = Depends(get_db),
) -> Project:
    project = await ProjectRepository.get_by_id(db, project_id, current_user.id)
    if project is None:
        raise RedirectException("/projects")
    return project