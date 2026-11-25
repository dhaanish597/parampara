"""PostgreSQL repository for sessions, step_events, calibration, mastery, and runs (T-016)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from parampara.db.pool import open_db
from parampara.db.repos.sessions import SessionRecord
from parampara.domain.generated import (
    Calibration,
    Mode,
    SessionSummary,
    SkillGraph,
    Status2,
    StepEvent,
    Type,
)
from parampara.tools.bkt import RunRecord


async def insert_session_db(database_url: str, record: SessionRecord, live_model: str) -> None:
    """Persist a new session row (and owning placeholder clip row) in PostgreSQL."""
    async with open_db(database_url) as conn, conn.transaction():
        if record.clip_id is not None:
            await conn.execute(
                "INSERT INTO clips (id, org_id, owner_user_id, kind, storage_path, mime) "
                "VALUES (%s, %s, %s, 'session', %s, 'video/webm') ON CONFLICT (id) DO NOTHING",
                (
                    record.clip_id,
                    record.org_id,
                    record.trainee_user_id,
                    f"clips/{record.clip_id}.webm",
                ),
            )
        await conn.execute(
            "INSERT INTO sessions "
            "(id, org_id, skill_version_id, trainee_user_id, mode, status, clip_id, live_model) "
            "VALUES (%s, %s, %s, %s, %s::session_mode, %s::session_status, %s, %s)",
            (
                record.id,
                record.org_id,
                record.skill_version_id,
                record.trainee_user_id,
                record.mode.value,
                record.status,
                record.clip_id,
                live_model,
            ),
        )


def _parse_events(
    session_id: UUID, ev_rows: list[dict[str, Any]]
) -> tuple[list[StepEvent], dict[str, list[int]]]:
    events: list[StepEvent] = []
    vlm_keys: dict[str, list[int]] = {}
    for er in ev_rows:
        payload = dict(er["payload"] or {})
        ev_type = Type(str(er["type"]))
        step_id = str(er["step_id"]) if er["step_id"] else None
        if ev_type == Type.vlm_key and payload.get("_server_verified") is True and step_id:
            vlm_keys.setdefault(step_id, []).append(int(er["t_ms"]))
        events.append(
            StepEvent(
                session_id=session_id,
                step_id=step_id,
                type=ev_type,
                t_ms=int(er["t_ms"]),
                payload=payload,
                frame_sha256=er["frame_sha256"],
            )
        )
    return events, vlm_keys


async def load_session_db(database_url: str, session_id: UUID) -> SessionRecord | None:
    """Load a session, its skill graph, and all step_events from PostgreSQL."""
    async with open_db(database_url) as conn:
        row = await (
            await conn.execute(
                "SELECT s.id, s.org_id, s.skill_version_id, s.trainee_user_id, "
                "s.mode::text AS mode, s.status::text AS status, "
                "s.calibration, s.summary, s.clip_id, sv.graph "
                "FROM sessions s JOIN skill_versions sv ON sv.id = s.skill_version_id "
                "WHERE s.id = %s",
                (session_id,),
            )
        ).fetchone()
        if row is None:
            return None
        ev_rows = await (
            await conn.execute(
                "SELECT step_id, type, t_ms, payload, frame_sha256 "
                "FROM step_events WHERE session_id = %s ORDER BY id ASC",
                (session_id,),
            )
        ).fetchall()
    events, server_vlm_keys = _parse_events(session_id, [dict(r) for r in ev_rows])
    return SessionRecord(
        id=UUID(str(row["id"])),
        org_id=UUID(str(row["org_id"])),
        skill_version_id=UUID(str(row["skill_version_id"])),
        trainee_user_id=UUID(str(row["trainee_user_id"])),
        mode=Mode(str(row["mode"])),
        graph=SkillGraph.model_validate(row["graph"]),
        status=str(row["status"]),
        calibration=Calibration.model_validate(row["calibration"]) if row["calibration"] else None,
        events=events,
        server_vlm_keys=server_vlm_keys,
        summary=SessionSummary.model_validate(row["summary"]) if row["summary"] else None,
        clip_id=UUID(str(row["clip_id"])) if row["clip_id"] else None,
    )


async def save_calibration_db(database_url: str, session_id: UUID, body: Calibration) -> None:
    async with open_db(database_url) as conn, conn.transaction():
        await conn.execute(
            "UPDATE sessions SET calibration = %s::jsonb WHERE id = %s",
            (body.model_dump_json(), session_id),
        )


async def insert_step_events_db(
    database_url: str,
    session_id: UUID,
    events: list[StepEvent],
    *,
    server_verified: bool = False,
) -> None:
    sql = (
        "INSERT INTO step_events (session_id, step_id, type, t_ms, payload, frame_sha256) "
        "VALUES (%s, %s, %s, %s, %s::jsonb, %s)"
    )
    async with open_db(database_url) as conn, conn.transaction():
        for ev in events:
            payload: dict[str, Any] = dict(ev.payload)
            if server_verified:
                payload["_server_verified"] = True
            await conn.execute(
                sql,
                (
                    session_id,
                    ev.step_id,
                    ev.type.value,
                    ev.t_ms,
                    json.dumps(payload),
                    ev.frame_sha256,
                ),
            )


async def load_user_mastery_db(
    database_url: str, user_id: UUID, skill_version_id: UUID
) -> dict[str, float]:
    sql = "SELECT step_id, p_learned FROM mastery WHERE user_id = %s AND skill_version_id = %s"
    async with open_db(database_url) as conn:
        rows = await (await conn.execute(sql, (user_id, skill_version_id))).fetchall()
    return {str(r["step_id"]): float(r["p_learned"]) for r in rows}


async def load_completed_runs_db(
    database_url: str, user_id: UUID, skill_version_id: UUID
) -> list[RunRecord]:
    sql = (
        "SELECT mode::text AS mode, summary FROM sessions "
        "WHERE trainee_user_id = %s AND skill_version_id = %s "
        "AND status = 'completed' AND summary IS NOT NULL "
        "ORDER BY ended_at ASC NULLS LAST, started_at ASC"
    )
    async with open_db(database_url) as conn:
        rows = await (await conn.execute(sql, (user_id, skill_version_id))).fetchall()
    return [
        RunRecord(clean_run=bool((r["summary"] or {}).get("clean_run", False)), mode=str(r["mode"]))
        for r in rows
    ]


async def save_completion_db(
    database_url: str,
    *,
    session_id: UUID,
    user_id: UUID,
    skill_version_id: UUID,
    status: Status2,
    clip_id: UUID | None,
    summary: SessionSummary,
    mastery_updates: dict[str, float],
) -> None:
    upsert_sql = (
        "INSERT INTO mastery "
        "(user_id, skill_version_id, step_id, p_learned, observations, updated_at) "
        "VALUES (%s, %s, %s, %s, 1, now()) "
        "ON CONFLICT (user_id, skill_version_id, step_id) DO UPDATE SET "
        "p_learned = EXCLUDED.p_learned, observations = mastery.observations + 1, "
        "updated_at = now()"
    )
    async with open_db(database_url) as conn, conn.transaction():
        for step_id, p_learned in mastery_updates.items():
            await conn.execute(upsert_sql, (user_id, skill_version_id, step_id, p_learned))
        await conn.execute(
            "UPDATE sessions SET status = %s::session_status, "
            "clip_id = COALESCE(%s, clip_id), summary = %s::jsonb, ended_at = now() WHERE id = %s",
            (status.value, clip_id, summary.model_dump_json(), session_id),
        )
