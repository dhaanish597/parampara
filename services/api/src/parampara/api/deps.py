"""FastAPI auth and role-checking dependencies (BUILD_PLAN 12.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, Header

from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings
from parampara.db.pool import open_db, resolve_database_url

ALL_DEMO_ROLES = ("owner", "supervisor", "master", "trainee", "lab_buyer")
ALLOWED_ASYMMETRIC_ALGS = ("RS256", "ES256", "EdDSA")
SUPABASE_AUDIENCE = "authenticated"


@dataclass
class CurrentUser:
    user_id: UUID
    display_name: str
    pseudonym: str
    preferred_lang: str = "hi"
    is_anonymous: bool = False
    memberships: dict[UUID, set[str]] = field(default_factory=dict)


@lru_cache(maxsize=8)
def _jwk_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300)


def _jwks_url(settings: Settings) -> str:
    if settings.supabase_jwt_issuer:
        return f"{settings.supabase_jwt_issuer.rstrip('/')}/.well-known/jwks.json"
    if settings.supabase_url:
        return f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return ""


def _signing_key(token: str, alg: str, settings: Settings) -> tuple[Any, list[str]]:
    """Return the verification key and allowed algorithms for this token's header alg."""
    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise AppError(status_code=401, code="invalid_token", message="HS256 not enabled")
        return settings.supabase_jwt_secret, ["HS256"]
    if alg in ALLOWED_ASYMMETRIC_ALGS:
        url = _jwks_url(settings)
        if not url:
            raise AppError(status_code=401, code="invalid_token", message="JWKS not configured")
        return _jwk_client(url).get_signing_key_from_jwt(token).key, list(ALLOWED_ASYMMETRIC_ALGS)
    raise AppError(status_code=401, code="invalid_token", message="Unsupported JWT alg")


def verify_supabase_jwt(token: str, settings: Settings) -> dict[str, Any]:
    """Cryptographically verify a Supabase JWT via JWKS (or local HS256 secret)."""
    try:
        alg = str(jwt.get_unverified_header(token).get("alg", ""))
    except jwt.PyJWTError as exc:
        raise AppError(status_code=401, code="invalid_token", message="Malformed JWT") from exc
    if not alg or alg.lower() == "none":
        raise AppError(status_code=401, code="invalid_token", message="Unsigned JWT rejected")
    try:
        key, algorithms = _signing_key(token, alg, settings)
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=SUPABASE_AUDIENCE,
            issuer=settings.supabase_jwt_issuer or None,
            options={"require": ["sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise AppError(status_code=401, code="invalid_token", message="Invalid JWT") from exc
    return dict(claims)


async def _load_user_from_db(uid: UUID, is_anonymous: bool, database_url: str) -> CurrentUser:
    url = resolve_database_url(database_url)
    if not url:
        return CurrentUser(
            user_id=uid,
            display_name="Worker",
            pseudonym=f"worker_{str(uid)[:8]}",
            is_anonymous=is_anonymous,
            memberships={},
        )
    async with open_db(url) as conn:
        prof = await (
            await conn.execute(
                "SELECT display_name, pseudonym, preferred_lang FROM profiles WHERE id = %s",
                (uid,),
            )
        ).fetchone()
        rows = await (
            await conn.execute(
                "SELECT org_id, role::text AS role FROM memberships WHERE user_id = %s",
                (uid,),
            )
        ).fetchall()
    memberships: dict[UUID, set[str]] = {}
    for row in rows:
        memberships.setdefault(UUID(str(row["org_id"])), set()).add(str(row["role"]))
    return CurrentUser(
        user_id=uid,
        display_name=str(prof["display_name"]) if prof else "Worker",
        pseudonym=str(prof["pseudonym"]) if prof else f"worker_{str(uid)[:8]}",
        preferred_lang=str(prof["preferred_lang"]) if prof else "hi",
        is_anonymous=is_anonymous,
        memberships=memberships,
    )


async def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(status_code=401, code="unauthorized", message="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    claims = verify_supabase_jwt(token, settings)
    try:
        uid = UUID(str(claims["sub"]))
    except ValueError as exc:
        raise AppError(status_code=401, code="invalid_token", message="Invalid sub claim") from exc
    is_anon = bool(claims.get("is_anonymous", False))
    return await _load_user_from_db(uid, is_anon, settings.database_url)


async def grant_demo_roles_in_db(user: CurrentUser, org_id: UUID, database_url: str) -> list[str]:
    """Insert profile and demo org memberships in PostgreSQL for an anonymous Supabase user."""
    url = resolve_database_url(database_url)
    if not url:
        raise AppError(status_code=503, code="db_unavailable", message="Database is not configured")
    async with open_db(url) as conn, conn.transaction():
        await conn.execute(
            "INSERT INTO auth.users (id, email) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            (user.user_id, f"anon-{str(user.user_id)[:8]}@demo.parampara.app"),
        )
        await conn.execute(
            "INSERT INTO profiles (id, display_name, pseudonym, preferred_lang) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (user.user_id, user.display_name, user.pseudonym, user.preferred_lang),
        )
        for role in ALL_DEMO_ROLES:
            await conn.execute(
                "INSERT INTO memberships (org_id, user_id, role) "
                "VALUES (%s, %s, %s::member_role) ON CONFLICT DO NOTHING",
                (org_id, user.user_id, role),
            )
    user.memberships[org_id] = set(ALL_DEMO_ROLES)
    return list(ALL_DEMO_ROLES)


def require_role(user: CurrentUser, org_id: UUID, allowed_roles: set[str]) -> None:
    user_roles = user.memberships.get(org_id, set())
    if not user_roles:
        raise AppError(status_code=403, code="forbidden", message="Not a member of this org")
    if allowed_roles and not (user_roles & allowed_roles):
        raise AppError(
            status_code=403,
            code="forbidden",
            message=f"Requires one of roles: {sorted(allowed_roles)}",
        )
