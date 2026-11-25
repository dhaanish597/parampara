"""Idempotent minimal seed for Parampara (BUILD_PLAN 11.5, T-010 AC3)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

import psycopg

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_GRAPH = ROOT / "contracts" / "fixtures" / "skill-graph.terminal-wiring.json"

PLATFORM_ORG_ID = UUID("10000000-0000-4000-8000-000000000001")
DEMO_ORG_ID = UUID("10000000-0000-4000-8000-000000000002")
LAB_ORG_ID = UUID("10000000-0000-4000-8000-000000000003")

DEMO_USERS = [
    (UUID("20000000-0000-4000-8000-000000000001"), "Ramesh (demo)", "ramesh_master", "master", DEMO_ORG_ID, "ramesh@demo.parampara.app", "ramesh@upi"),
    (UUID("20000000-0000-4000-8000-000000000002"), "Sunita (demo)", "sunita_sup", "supervisor", DEMO_ORG_ID, "sunita@demo.parampara.app", "sunita@upi"),
    (UUID("20000000-0000-4000-8000-000000000003"), "Pooja (demo)", "pooja_trainee", "trainee", DEMO_ORG_ID, "pooja@demo.parampara.app", "pooja@upi"),
    (UUID("20000000-0000-4000-8000-000000000004"), "Arjun (demo)", "arjun_trainee", "trainee", DEMO_ORG_ID, "arjun@demo.parampara.app", "arjun@upi"),
    (UUID("20000000-0000-4000-8000-000000000005"), "Owner (demo)", "indore_owner", "owner", DEMO_ORG_ID, "owner@demo.parampara.app", None),
    (UUID("20000000-0000-4000-8000-000000000006"), "Lab Buyer (demo)", "demo_lab_buyer", "lab_buyer", LAB_ORG_ID, "lab@demo.parampara.app", None),
]

DEMO_SKILL_ID = UUID("30000000-0000-4000-8000-000000000001")
DEMO_SKILL_VERSION_ID = UUID("30000000-0000-4000-8000-000000000002")


def seed(database_url: str) -> None:
    graph_text = FIXTURE_GRAPH.read_text(encoding="utf-8")
    graph_sha256 = hashlib.sha256(graph_text.encode("utf-8")).hexdigest()
    graph_json = json.dumps(json.loads(graph_text))

    with psycopg.connect(database_url, autocommit=False) as conn, conn.cursor() as cur:
        cur.execute(
            """
            insert into orgs (id, name, city, kind, is_demo) values
              (%s, 'Parampara', 'Indore', 'platform', false),
              (%s, 'Indore Electrical Training Centre (Demo)', 'Indore', 'training_centre', true),
              (%s, 'Demo Robotics Lab', 'Bengaluru', 'lab', true)
            on conflict (id) do nothing
            """,
            (PLATFORM_ORG_ID, DEMO_ORG_ID, LAB_ORG_ID),
        )
        for uid, name, pseudonym, role, org_id, email, upi in DEMO_USERS:
            cur.execute(
                "insert into auth.users (id, email) values (%s, %s) on conflict (id) do nothing",
                (uid, email),
            )
            cur.execute(
                """
                insert into profiles (id, display_name, pseudonym, preferred_lang, upi_vpa)
                values (%s, %s, %s, 'hi', %s)
                on conflict (id) do nothing
                """,
                (uid, name, pseudonym, upi),
            )
            cur.execute(
                """
                insert into memberships (org_id, user_id, role)
                values (%s, %s, %s::member_role)
                on conflict do nothing
                """,
                (org_id, uid, role),
            )

        ramesh_id = DEMO_USERS[0][0]
        sunita_id = DEMO_USERS[1][0]
        cur.execute(
            """
            insert into skills (id, org_id, slug, current_version, created_by)
            values (%s, %s, 'terminal-wiring', 1, %s)
            on conflict (org_id, slug) do nothing
            """,
            (DEMO_SKILL_ID, DEMO_ORG_ID, ramesh_id),
        )
        cur.execute(
            """
            insert into skill_versions
              (id, skill_id, version, status, graph, author_user_id, approved_by, approved_at, graph_sha256)
            values
              (%s, %s, 1, 'approved', %s::jsonb, %s, %s, now(), %s)
            on conflict (skill_id, version) do nothing
            """,
            (DEMO_SKILL_VERSION_ID, DEMO_SKILL_ID, graph_json, ramesh_id, sunita_id, graph_sha256),
        )
        conn.commit()


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    seed(url)
    print("Minimal seed applied cleanly.")
