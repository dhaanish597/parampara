/** Typed calls per route. The only place response casts live until routes declare models. */
import { unwrap } from "./client";
import type { ApiClient } from "./client";
import type { Me, SkillVersionSummary } from "./types";

// TODO(T-011): drop the casts once the API declares Pydantic response models (D-012).
export async function getMe(api: ApiClient): Promise<Me> {
  return unwrap(await api.GET("/v1/me")) as unknown as Me;
}

export async function joinDemo(api: ApiClient): Promise<void> {
  unwrap(await api.POST("/v1/demo/join"));
}

export async function listSkillVersions(api: ApiClient, orgId: string): Promise<SkillVersionSummary[]> {
  const res = await api.GET("/v1/skill-versions", { params: { query: { org_id: orgId } } });
  return (unwrap(res) as unknown as { items: SkillVersionSummary[] }).items;
}
