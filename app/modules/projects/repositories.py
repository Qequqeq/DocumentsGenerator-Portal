# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.projects.models import Project


class ProjectRepository:

    @staticmethod
    def get_user_projects_dir(user_id: int) -> Path:
        settings = get_settings()
        uploads_dir = settings.base_dir / "uploads"
        user_dir = uploads_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    @staticmethod
    def get_project_dir(user_id: int, project_id: str) -> Path:
        user_dir = ProjectRepository.get_user_projects_dir(user_id)
        project_dir = user_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    @staticmethod
    async def create(
            db: AsyncSession,
            user_id: int,
            org_name: Optional[str] = None,
            doc_date: Optional[str] = None,
    ) -> Project:
        project_id = str(uuid.uuid4())

        project = Project(
            id=project_id,
            user_id=user_id,
            org_name=org_name,
            doc_date=doc_date,
            status="draft",
            workers_count=0,
            generated_count=0,
            risk_inputs={},
            generated_cards=[],
        )
        ProjectRepository.get_project_dir(user_id, project_id)

        db.add(project)
        await db.flush()
        await db.refresh(project)
        return project

    @staticmethod
    async def get_by_id(
            db: AsyncSession,
            project_id: str,
            user_id: int,
    ) -> Optional[Project]:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_user(
            db: AsyncSession,
            user_id: int,
    ) -> List[Project]:
        result = await db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.updated_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def update(
            db: AsyncSession,
            project: Project,
    ) -> Project:
        await db.flush()
        await db.refresh(project)
        return project

    @staticmethod
    async def delete(
            db: AsyncSession,
            project_id: str,
            user_id: int,
    ) -> bool:
        project = await ProjectRepository.get_by_id(db, project_id, user_id)
        if project is None:
            return False

        project_dir = ProjectRepository.get_project_dir(user_id, project_id)
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir, ignore_errors=True)

        await db.execute(
            delete(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
        await db.commit()
        return True

    @staticmethod
    async def update_status(
            db: AsyncSession,
            project_id: str,
            user_id: int,
            status: str,
    ) -> Optional[Project]:
        result = await db.execute(
            update(Project)
            .where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
            .values(status=status, updated_at=datetime.now())
            .returning(Project)
        )
        await db.commit()
        return result.scalar_one_or_none()