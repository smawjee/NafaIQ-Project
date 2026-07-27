import { describe, expect, it } from "vitest";
import { hasPermission } from "./permissions";
import { formatPkt } from "@/features/admin/components/ui";
import type { AdminMe } from "./types";

const superAdmin: AdminMe = {
  user_id: "1",
  email: "a@x.com",
  roles: ["super_admin"],
  permissions: [],
};
const support: AdminMe = {
  user_id: "2",
  email: "b@x.com",
  roles: ["support_admin"],
  permissions: ["users.read", "users.suspend"],
};

describe("hasPermission", () => {
  it("grants everything to super_admin regardless of listed permissions", () => {
    expect(hasPermission(superAdmin, "flags.write")).toBe(true);
    expect(hasPermission(superAdmin, "anything.at.all")).toBe(true);
  });

  it("grants only mapped permissions to a scoped admin", () => {
    expect(hasPermission(support, "users.suspend")).toBe(true);
    expect(hasPermission(support, "flags.write")).toBe(false);
  });

  it("denies a non-admin (null)", () => {
    expect(hasPermission(null, "users.read")).toBe(false);
  });
});

describe("formatPkt", () => {
  it("returns an em dash for null/invalid input", () => {
    expect(formatPkt(null)).toBe("—");
    expect(formatPkt(undefined)).toBe("—");
    expect(formatPkt("not-a-date")).toBe("—");
  });

  it("formats a valid ISO timestamp in the Karachi zone", () => {
    // 2026-07-27T00:00:00Z → 05:00 PKT (UTC+5), same calendar day.
    const out = formatPkt("2026-07-27T00:00:00Z");
    expect(out).toContain("2026");
    expect(out).toContain("Jul");
    expect(out).toContain("05:00");
  });
});
