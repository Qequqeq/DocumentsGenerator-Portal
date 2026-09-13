# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.solutions.models import Solution
from app.shared.text import safe_filename, translit


class SolutionService:
    @staticmethod
    def solutions_dir() -> Path:
        d = get_settings().solutions_dir
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _base_slug(position: str) -> str:
        base = translit(position).lower().replace(" ", "-")
        base = safe_filename(base)
        base = re.sub(r"\.+", "-", base)
        base = re.sub(r"-+", "-", base).strip("-")
        return base or "solution"

    @staticmethod
    async def ensure_unique_slug(db: AsyncSession, position: str, exclude_id: Optional[int] = None) -> str:
        base = SolutionService._base_slug(position)
        slug = base
        n = 2
        while True:
            stmt = select(Solution.id).where(Solution.slug == slug)
            if exclude_id is not None:
                stmt = stmt.where(Solution.id != exclude_id)
            res = await db.execute(stmt)
            if res.scalar_one_or_none() is None:
                return slug
            slug = f"{base}-{n}"
            n += 1

    @staticmethod
    async def list_solutions(
        db: AsyncSession,
        status: str = "",
        q: str = "",
    ) -> List[Solution]:
        stmt = select(Solution).order_by(Solution.position)
        if status == "published":
            stmt = stmt.where(Solution.is_published.is_(True))
        elif status == "draft":
            stmt = stmt.where(Solution.is_published.is_(False))
        if q:
            stmt = stmt.where(Solution.position.ilike(f"%{q}%"))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_solution(
        db: AsyncSession,
        *,
        position: str,
        category: str,
        description: str,
        detailed_description: str,
        is_published: bool,
        json_bytes: bytes,
        pdf_bytes: Optional[bytes] = None,
    ) -> Solution:
        slug = await SolutionService.ensure_unique_slug(db, position)
        directory = SolutionService.solutions_dir()

        json_name = f"{slug}.json"
        (directory / json_name).write_bytes(json_bytes)

        pdf_name = None
        if pdf_bytes:
            pdf_name = f"{slug}.pdf"
            (directory / pdf_name).write_bytes(pdf_bytes)

        solution = Solution(
            slug=slug,
            position=position,
            category=category,
            description=description,
            detailed_description=detailed_description,
            template_path=json_name,
            sample_pdf_path=pdf_name,
            is_published=is_published,
        )
        db.add(solution)
        await db.flush()
        await db.refresh(solution)
        return solution

    @staticmethod
    async def update_solution(
        db: AsyncSession,
        solution: Solution,
        *,
        position: str,
        category: str,
        description: str,
        detailed_description: str,
        is_published: bool,
        json_bytes: Optional[bytes] = None,
        pdf_bytes: Optional[bytes] = None,
    ) -> Solution:
        directory = SolutionService.solutions_dir()

        if json_bytes:
            (directory / solution.template_path).write_bytes(json_bytes)
        if pdf_bytes:
            pdf_name = solution.sample_pdf_path or f"{solution.slug}.pdf"
            (directory / pdf_name).write_bytes(pdf_bytes)
            solution.sample_pdf_path = pdf_name

        solution.position = position
        solution.category = category
        solution.description = description
        solution.detailed_description = detailed_description
        solution.is_published = is_published
        await db.flush()
        await db.refresh(solution)
        return solution

    @staticmethod
    async def delete_solution(db: AsyncSession, solution: Solution) -> None:
        directory = SolutionService.solutions_dir()
        for name in (solution.template_path, solution.sample_pdf_path):
            if name:
                path = directory / name
                if path.exists():
                    path.unlink()
        await db.delete(solution)
        await db.flush()

    @staticmethod
    def read_template(solution: Solution) -> dict:
        path = SolutionService.solutions_dir() / solution.template_path
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    async def list_published(
        db: AsyncSession,
        q: str = "",
        category: str = "",
        letter: str = "",
        page: int = 1,
        per_page: int = 24,
    ):
        from sqlalchemy import func as sa_func

        base = [Solution.is_published.is_(True)]
        if q:
            base.append(Solution.position.ilike(f"%{q}%"))
        if category:
            base.append(Solution.category == category)
        if letter:
            base.append(Solution.position.ilike(f"{letter}%"))

        count_stmt = select(sa_func.count(Solution.id))
        for cond in base:
            count_stmt = count_stmt.where(cond)
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = select(Solution)
        for cond in base:
            stmt = stmt.where(cond)
        stmt = stmt.order_by(Solution.position).offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def available_letters(db: AsyncSession):
        from sqlalchemy import func as sa_func

        stmt = select(
            sa_func.upper(sa_func.substr(Solution.position, 1, 1))
        ).where(Solution.is_published.is_(True))
        result = await db.execute(stmt)
        return {row[0] for row in result.all() if row[0]}

    @staticmethod
    async def get_by_slug(db: AsyncSession, slug: str):
        stmt = select(Solution).where(Solution.slug == slug)
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def list_published_grouped(db: AsyncSession):
        stmt = (
            select(Solution)
            .where(Solution.is_published.is_(True))
            .order_by(Solution.position)
        )
        result = await db.execute(stmt)
        grouped = {}
        for solution in result.scalars().all():
            grouped.setdefault(solution.category or "", []).append(solution)
        return grouped

    @staticmethod
    def build_preview(solution: Solution) -> dict:
        """Состав оценки из JSON шаблона (файл наружу не отдаётся)."""
        from app.modules.settings.risk_catalog import DANGER_DATABASE, RISK_DATABASE

        def sort_key(item):
            return [int(p) for p in str(item[0]).split(".") if p.isdigit()] or [0]

        raw = SolutionService.read_template(solution).get("risks", {}) or {}
        dangers = []
        total_risks = 0

        for d_key, r_dict in sorted(raw.items(), key=sort_key):
            try:
                d_id = int(float(d_key))
            except (TypeError, ValueError):
                continue
            danger = DANGER_DATABASE.get(d_id)

            risks = []
            for r_key, vals in sorted((r_dict or {}).items(), key=sort_key):
                if not isinstance(vals, dict):
                    continue
                deg = int(vals.get("deg", vals.get("degree", 0)))
                ch = int(vals.get("ch", vals.get("chance", 1)))
                kef = float(vals.get("kef", vals.get("coeff", 0.0)))
                risk_tpl = RISK_DATABASE.get(str(r_key))
                risks.append({
                    "number": str(r_key),
                    "name": risk_tpl.risk_name if risk_tpl else str(r_key),
                    "deg": deg,
                    "ch": ch,
                    "kef": kef,
                    "value": round(deg * ch * kef, 1),
                })

            if risks:
                total_risks += len(risks)
                dangers.append({
                    "number": str(danger.danger_number) if danger else str(d_key),
                    "name": danger.danger_name if danger else f"Опасность {d_key}",
                    "risks": risks,
                    "total": round(sum(r["value"] for r in risks), 1),
                })

        return {"dangers": dangers, "total_risks": total_risks}