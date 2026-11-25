"""PostgreSQL repository for licences, royalty_events, and payouts (BUILD_PLAN 23.1, T-042)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from parampara.api.errors import AppError
from parampara.api.settings import Settings
from parampara.db.pool import open_db
from parampara.domain.generated import Licence, Payout, RoyaltyEvent
from parampara.tools.payouts import create_payout
from parampara.tools.royalty import (
    RoyaltyShare,
    build_fixed_licence_terms,
    generate_watermark_id,
    split_royalties,
)


async def _load_dataset_ctx(conn: Any, dataset_id: UUID) -> dict[str, Any]:
    ds_sql = (
        "SELECT d.id, d.scope, d.export_path, sv.author_user_id, sv.approved_by, "
        "sv.parent_version_id, s.org_id AS factory_org_id "
        "FROM datasets d JOIN skill_versions sv ON sv.id = d.skill_version_id "
        "JOIN skills s ON s.id = sv.skill_id WHERE d.id = %s"
    )
    ds = await (await conn.execute(ds_sql, (dataset_id,))).fetchone()
    if ds is None:
        raise AppError(status_code=404, code="not_found", message="Dataset not found")
    plat = await (
        await conn.execute("SELECT id FROM orgs WHERE kind = 'platform' LIMIT 1")
    ).fetchone()
    if plat is None:
        raise AppError(status_code=500, code="platform_missing", message="Platform org not seeded")
    ep_rows = await (
        await conn.execute(
            "SELECT contributor_user_id, count(*)::int AS cnt FROM dataset_episodes "
            "WHERE dataset_id = %s AND role = 'trainee' GROUP BY contributor_user_id",
            (dataset_id,),
        )
    ).fetchall()
    parent_master: UUID | None = None
    if ds["parent_version_id"]:
        prow = await (
            await conn.execute(
                "SELECT author_user_id FROM skill_versions WHERE id = %s",
                (ds["parent_version_id"],),
            )
        ).fetchone()
        if prow:
            parent_master = UUID(str(prow["author_user_id"]))
    return {
        "platform_org_id": UUID(str(plat["id"])),
        "factory_org_id": UUID(str(ds["factory_org_id"])),
        "master_user_id": UUID(str(ds["author_user_id"])),
        "reviewer_user_id": UUID(str(ds["approved_by"] or ds["author_user_id"])),
        "parent_master_user_id": parent_master,
        "trainee_episodes": {UUID(str(r["contributor_user_id"])): int(r["cnt"]) for r in ep_rows},
    }


async def _insert_payout(
    conn: Any, re_id: UUID, sh: RoyaltyShare, settings: Settings
) -> Payout | None:
    if sh.beneficiary_user_id is None:
        return None
    vpa_row = await (
        await conn.execute("SELECT upi_vpa FROM profiles WHERE id = %s", (sh.beneficiary_user_id,))
    ).fetchone()
    payout = create_payout(
        royalty_event_id=re_id,
        beneficiary_vpa=str(vpa_row["upi_vpa"]) if vpa_row and vpa_row["upi_vpa"] else None,
        amount_paise=sh.amount_paise,
        provider=settings.payout_provider,
    )
    await conn.execute(
        "INSERT INTO payouts (id, royalty_event_id, provider, provider_ref, status, raw) "
        "VALUES (%s, %s, %s::payout_provider, %s, %s, %s::jsonb)",
        (
            payout.id,
            re_id,
            payout.provider.value,
            payout.provider_ref,
            payout.status.value,
            json.dumps({"provider_ref": payout.provider_ref}),
        ),
    )
    return payout


async def _insert_royalty_and_payout(
    conn: Any, lic_id: UUID, sh: RoyaltyShare, created_at: datetime, settings: Settings
) -> tuple[RoyaltyEvent, Payout | None]:
    re_id = uuid4()
    await conn.execute(
        "INSERT INTO royalty_events "
        "(id, licence_id, role, beneficiary_user_id, beneficiary_org_id, amount_paise, basis) "
        "VALUES (%s, %s, %s::royalty_role, %s, %s, %s, %s::jsonb)",
        (
            re_id,
            lic_id,
            sh.role.value,
            sh.beneficiary_user_id,
            sh.beneficiary_org_id,
            sh.amount_paise,
            json.dumps(sh.basis),
        ),
    )
    ev = RoyaltyEvent(
        id=re_id,
        licence_id=lic_id,
        role=sh.role,
        beneficiary_user_id=sh.beneficiary_user_id,
        beneficiary_org_id=sh.beneficiary_org_id,
        amount_paise=sh.amount_paise,
        basis=sh.basis,
        created_at=created_at,
    )
    return ev, await _insert_payout(conn, re_id, sh, settings)


async def _apply_shares(
    conn: Any,
    lic_id: UUID,
    price_paise: int,
    ctx: dict[str, Any],
    created_at: datetime,
    settings: Settings,
) -> tuple[list[RoyaltyEvent], list[Payout]]:
    events: list[RoyaltyEvent] = []
    payouts: list[Payout] = []
    for sh in split_royalties(price_paise=price_paise, **ctx):
        ev, payout = await _insert_royalty_and_payout(conn, lic_id, sh, created_at, settings)
        events.append(ev)
        if payout is not None:
            payouts.append(payout)
    return events, payouts


async def persist_licence_tx(
    url: str, body: Any, actor_user_id: UUID, settings: Settings
) -> tuple[Licence, list[RoyaltyEvent], list[Payout]]:
    """Atomically insert licence, royalty_events, and test payouts in one DB transaction."""
    terms = build_fixed_licence_terms(body.scope)
    wm, lic_id = generate_watermark_id(), uuid4()
    lic_sql = (
        "INSERT INTO licences "
        "(id, dataset_id, buyer_org_id, price_paise, terms, watermark_id, created_by) "
        "VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s) RETURNING created_at"
    )
    params = (
        lic_id,
        body.dataset_id,
        body.buyer_org_id,
        body.price_paise,
        terms.model_dump_json(),
        wm,
        actor_user_id,
    )
    async with open_db(url) as conn, conn.transaction():
        ctx = await _load_dataset_ctx(conn, body.dataset_id)
        lic_row = await (await conn.execute(lic_sql, params)).fetchone()
        if lic_row is None:
            raise RuntimeError("Failed to insert licence row")
        created_at: datetime = lic_row["created_at"]
        events, payouts = await _apply_shares(
            conn, lic_id, body.price_paise, ctx, created_at, settings
        )
    lic = Licence(
        id=lic_id,
        dataset_id=body.dataset_id,
        buyer_org_id=body.buyer_org_id,
        price_paise=body.price_paise,
        terms=terms,
        watermark_id=wm,
        created_at=created_at,
    )
    return lic, events, payouts
