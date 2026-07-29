import { useAuth } from "@/hooks/use-auth";
import { useNavigate } from "@tanstack/react-router";
import { DEMO_EMAIL, isDemoUser } from "@/lib/demo";

export { DEMO_EMAIL, isDemoUser };

export function useDemo() {
  const { user, signInWithPassword } = useAuth();
  const navigate = useNavigate();

  const isDemo = isDemoUser(user);

  const signInAsDemo = async (options?: { redirectTo?: string }) => {
    const demoPassword = import.meta.env.VITE_DEMO_PASSWORD || "";
    if (!demoPassword) {
      throw new Error("Demo password not configured");
    }
    const result = await signInWithPassword(DEMO_EMAIL, demoPassword);
    if (result.error) {
      throw new Error(result.error);
    }
    navigate({ to: options?.redirectTo ?? "/app" });
    return result;
  };

  return { isDemo, signInAsDemo, demoEmail: DEMO_EMAIL };
}
