"""Profile and demo-join auth routes (BUILD_PLAN 12.2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from parampara.api.deps import CurrentUser, get_current_user, grant_demo_roles_in_db
from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings

router = APIRouter(prefix="/v1")


class ProfileView(BaseModel):
    id: UUID
    display_name: str
    pseudonym: str
    preferred_lang: str


class MembershipView(BaseModel):
    org_id: UUID
    roles: list[str]


class MeResponse(BaseModel):
    profile: ProfileView
    memberships: list[MembershipView]


class DemoJoinResponse(BaseModel):
    org_id: UUID
    roles: list[str]


@router.get("/me", response_model=MeResponse)
async def get_me(user: CurrentUser = Depends(get_current_user)) -> MeResponse:  # noqa: B008
    return MeResponse(
        profile=ProfileView(
            id=user.user_id,
            display_name=user.display_name,
            pseudonym=user.pseudonym,
            preferred_lang=user.preferred_lang,
        ),
        memberships=[
            MembershipView(org_id=oid, roles=sorted(roles))
            for oid, roles in user.memberships.items()
        ],
    )


@router.post("/demo/join", response_model=DemoJoinResponse)
async def demo_join(
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> DemoJoinResponse:
    if not user.is_anonymous:
        raise AppError(
            status_code=403,
            code="forbidden",
            message="Demo join is only allowed for anonymous Supabase users",
        )
    demo_org_id = UUID(settings.demo_org_id)
    roles = await grant_demo_roles_in_db(user, demo_org_id, settings.database_url)
    return DemoJoinResponse(org_id=demo_org_id, roles=roles)
