import type { Plan } from "@/lib/plan-features";

export function initial(name?: string | null, email?: string | null) {
  return (name?.trim()?.[0] || email?.trim()?.[0] || "U").toUpperCase();
}

/**
 * Plan-aware upgrade CTA. Free users are nudged to Pro, Pro users to Premium,
 * and Premium users (top tier) see no upgrade prompt. Keeps the header/drawer
 * honest instead of always showing "Upgrade to Pro".
 */
export function upgradeCta(plan: Plan): { label: string; show: boolean } {
  if (plan === "Premium") return { label: "", show: false };
  if (plan === "Pro") return { label: "Go Premium", show: true };
  return { label: "Upgrade to Pro", show: true };
}
