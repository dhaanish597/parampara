"""Exemplar API route module: skill versions (BUILD_PLAN 12.2 & 31.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from parampara.api.deps import CurrentUser, get_current_user, require_role
from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings
from parampara.db.repos.skill_versions import (
    SkillVersionRow,
    get_skill_version,
    list_skill_versions_for_org,
)
from parampara.domain.generated import SkillGraph

router = APIRouter(prefix="/v1")


class SkillVersionResponse(BaseModel):
    id: UUID
    skill_id: UUID
    org_id: UUID
    slug: str
    version: int
    status: str
    graph: SkillGraph
    author_user_id: UUID
    created_at: datetime


class SkillVersionListResponse(BaseModel):
    items: list[SkillVersionResponse]


def _serialize(row: SkillVersionRow) -> SkillVersionResponse:
    return SkillVersionResponse(
        id=row.id,
        skill_id=row.skill_id,
        org_id=row.org_id,
        slug=row.slug,
        version=row.version,
        status=row.status,
        graph=row.graph,
        author_user_id=row.author_user_id,
        created_at=row.created_at,
    )


@router.get("/skill-versions", response_model=SkillVersionListResponse)
async def list_skill_versions(
    org_id: Annotated[UUID | None, Query()] = None,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> SkillVersionListResponse:
    target_org = org_id or UUID(settings.demo_org_id)
    require_role(user, target_org, set())
    rows = await list_skill_versions_for_org(settings.database_url, target_org)
    return SkillVersionListResponse(items=[_serialize(r) for r in rows])


@router.get("/skill-versions/{version_id}", response_model=SkillVersionResponse)
async def get_skill_version_route(
    version_id: UUID,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> SkillVersionResponse:
    row = await get_skill_version(settings.database_url, version_id)
    if row is None:
        raise AppError(status_code=404, code="not_found", message="Skill version not found")
    require_role(user, row.org_id, set())
    return _serialize(row)
