/** Response shapes the API does not yet declare in OpenAPI (routes return untyped dicts). */
import type { SkillGraph } from "@parampara/contracts";

// TODO(T-011): replace with the generated OpenAPI response types once Gemini's routes declare
// Pydantic response models (D-012). Fields mirror routes/skill_versions.py `_serialize`.
export interface SkillVersionSummary {
  id: string;
  skill_id: string;
  org_id: string;
  slug: string;
  version: number;
  status: "draft" | "in_review" | "approved" | "retired";
  graph: SkillGraph;
  author_user_id: string;
  created_at: string;
}

export type MemberRole = "owner" | "supervisor" | "master" | "trainee" | "lab_buyer";

export interface Me {
  profile: { id: string; display_name: string; pseudonym: string; preferred_lang: string };
  memberships: { org_id: string; roles: MemberRole[] }[];
}
