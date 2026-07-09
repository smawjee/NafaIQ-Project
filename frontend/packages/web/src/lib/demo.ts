// Single source of truth for demo-account detection.
// The demo account is a real Supabase auth user identified by email; all of its
// app activity lives in the local Redux store and must never reach the backend.

export const DEMO_EMAIL: string = import.meta.env.VITE_DEMO_EMAIL || "demo@nafaiq.com";

export function isDemoUser(user: { email?: string | null } | null | undefined): boolean {
  return !!user && user.email === DEMO_EMAIL;
}
