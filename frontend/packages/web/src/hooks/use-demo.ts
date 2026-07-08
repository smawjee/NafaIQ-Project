import { useAuth } from "@/hooks/use-auth";

const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL || "demo@nafaiq.com";
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || "";

export function useDemo() {
  const { user, signInWithPassword } = useAuth();

  const isDemo = !!(user && user.email === DEMO_EMAIL);

  const signInAsDemo = async () => {
    if (!DEMO_PASSWORD) {
      throw new Error("Demo password not configured");
    }
    return signInWithPassword(DEMO_EMAIL, DEMO_PASSWORD);
  };

  return { isDemo, signInAsDemo, demoEmail: DEMO_EMAIL };
}
