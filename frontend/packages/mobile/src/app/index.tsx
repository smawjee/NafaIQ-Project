// Landing (public `/`) — the premium liquid-glass intro that resolves into the
// sign-in form. Authenticated users skip straight to the dashboard.
import { Redirect } from "expo-router";

import { AuthExperience } from "@/components/auth/AuthExperience";
import { useAuth } from "@/hooks/use-auth";

export default function Landing() {
  const { user, loading } = useAuth();
  if (!loading && user) return <Redirect href="/(tabs)/app" />;
  return <AuthExperience intro />;
}
