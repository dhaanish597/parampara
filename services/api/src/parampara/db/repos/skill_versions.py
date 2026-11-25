"""Plain-SQL repository for skill_versions (BUILD_PLAN 11.1 & 31.4).

Exemplar repository: plain SQL with psycopg 3, typed dataclasses, no ORM.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from parampara.domain.generated import SkillGraph

DEMO_SKILL_ID = UUID("30000000-0000-4000-8000-000000000001")
DEMO_SKILL_VERSION_ID = UUID("30000000-0000-4000-8000-000000000002")
DEMO_ORG_ID = UUID("10000000-0000-4000-8000-000000000002")
DEMO_AUTHOR_ID = UUID("20000000-0000-4000-8000-000000000001")
FIXTURE_PATH = (
    Path(__file__).resolve().parents[6]
    / "contracts"
    / "fixtures"
    / "skill-graph.terminal-wiring.json"
)


@dataclass(frozen=True)
class SkillVersionRow:
    id: UUID
    skill_id: UUID
    org_id: UUID
    slug: str
    version: int
    status: str
    graph: SkillGraph
    author_user_id: UUID
    created_at: datetime


SELECT_BY_ID_SQL = """
select sv.id, sv.skill_id, s.org_id, s.slug, sv.version, sv.status::text,
       sv.graph, sv.author_user_id, sv.created_at
from skill_versions sv
join skills s on s.id = sv.skill_id
where sv.id = %s
"""

LIST_BY_ORG_SQL = """
select sv.id, sv.skill_id, s.org_id, s.slug, sv.version, sv.status::text,
       sv.graph, sv.author_user_id, sv.created_at
from skill_versions sv
join skills s on s.id = sv.skill_id
where s.org_id = %s
order by s.slug asc, sv.version desc
"""


def _row_from_tuple(row: tuple[Any, ...]) -> SkillVersionRow:
    return SkillVersionRow(
        id=UUID(str(row[0])),
        skill_id=UUID(str(row[1])),
        org_id=UUID(str(row[2])),
        slug=str(row[3]),
        version=int(row[4]),
        status=str(row[5]),
        graph=SkillGraph.model_validate(row[6]),
        author_user_id=UUID(str(row[7])),
        created_at=row[8],
    )


def _fixture_skill_version() -> SkillVersionRow:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return SkillVersionRow(
        id=DEMO_SKILL_VERSION_ID,
        skill_id=DEMO_SKILL_ID,
        org_id=DEMO_ORG_ID,
        slug="terminal-wiring",
        version=1,
        status="approved",
        graph=SkillGraph.model_validate(raw),
        author_user_id=DEMO_AUTHOR_ID,
        created_at=datetime(2026, 11, 25, 10, 0, tzinfo=UTC),
    )


async def get_skill_version(database_url: str, version_id: UUID) -> SkillVersionRow | None:
    if not database_url:
        demo = _fixture_skill_version()
        return demo if version_id == demo.id else None
    async with await psycopg.AsyncConnection.connect(database_url) as conn, conn.cursor() as cur:
        await cur.execute(SELECT_BY_ID_SQL, (version_id,))
        row = await cur.fetchone()
        return _row_from_tuple(row) if row else None


async def list_skill_versions_for_org(database_url: str, org_id: UUID) -> list[SkillVersionRow]:
    if not database_url:
        demo = _fixture_skill_version()
        return [demo] if org_id == demo.org_id else []
    async with await psycopg.AsyncConnection.connect(database_url) as conn, conn.cursor() as cur:
        await cur.execute(LIST_BY_ORG_SQL, (org_id,))
        rows = await cur.fetchall()
        return [_row_from_tuple(r) for r in rows]
