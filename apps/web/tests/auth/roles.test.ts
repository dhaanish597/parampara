import { describe, expect, it } from "vitest";

import type { Me } from "../../lib/api/types";
import { pickActiveRole, primaryOrgId, rolesOf } from "../../lib/auth/roles";

const me: Me = {
  profile: { id: "u", display_name: "Judge", pseudonym: "judge_1", preferred_lang: "hi" },
  memberships: [{ org_id: "org", roles: ["owner", "trainee", "lab_buyer", "master", "supervisor"] }],
};

describe("roles", () => {
  it("orders held roles by journey", () => {
    expect(rolesOf(me)).toEqual(["master", "supervisor", "trainee", "lab_buyer", "owner"]);
    expect(rolesOf(null)).toEqual([]);
    expect(rolesOf(me, "other-org")).toEqual([]);
  });

  it("keeps a saved role only if it is still held", () => {
    expect(pickActiveRole(["master", "trainee"], "trainee")).toBe("trainee");
    expect(pickActiveRole(["master", "trainee"], "owner")).toBe("master");
    expect(pickActiveRole([], "owner")).toBeNull();
  });

  it("finds the primary org", () => {
    expect(primaryOrgId(me)).toBe("org");
    expect(primaryOrgId(null)).toBeNull();
  });
});
