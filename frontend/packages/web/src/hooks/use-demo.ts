import { useAuth } from "@/hooks/use-auth";
import { useNavigate } from "@tanstack/react-router";

const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL || "demo@nafaiq.com";
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || "";

export function useDemo() {
  const { user, signInWithPassword } = useAuth();
  const navigate = useNavigate();

  const isDemo = !!(user && user.email === DEMO_EMAIL);

  const signInAsDemo = async (options?: { redirectTo?: string }) => {
    if (!DEMO_PASSWORD) {
      throw new Error("Demo password not configured");
    }
    const result = await signInWithPassword(DEMO_EMAIL, DEMO_PASSWORD);
    if (!result.error) {
      navigate({ to: options?.redirectTo ?? "/app" });
    }
    return result;
  };

  return { isDemo, signInAsDemo, demoEmail: DEMO_EMAIL };
}
