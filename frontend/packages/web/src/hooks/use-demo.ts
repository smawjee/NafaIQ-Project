import { useAuth } from "@/hooks/use-auth";
import { useNavigate } from "@tanstack/react-router";
import { DEMO_EMAIL, isDemoUser } from "@/lib/demo";

export { DEMO_EMAIL, isDemoUser };

const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || "";

export function useDemo() {
  const { user, signInWithPassword } = useAuth();
  const navigate = useNavigate();

  const isDemo = isDemoUser(user);

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
