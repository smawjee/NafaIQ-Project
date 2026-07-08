// Auth route (`/auth`) — the gate redirects here when a session is required.
// Renders the same premium liquid-glass flow but skips the intro (straight to
// the form). On success the root AuthGate redirects to the dashboard.
import { AuthExperience } from "@/components/auth/AuthExperience";

export default function AuthScreen() {
  return <AuthExperience />;
}
