import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "@/integrations/supabase/client";
import { isDemoUser } from "@/lib/demo";
import { store, resetDemoData } from "@/store";
import { demoSessionStarted } from "@/store/demoUser";

export type Profile = {
  id: string;
  display_name: string | null;
  plan: string;
  plan_selected_at: string | null;
  avatar_url: string | null;
};

type AuthContextValue = {
  session: Session | null;
  user: User | null;
  profile: Profile | null;
  loading: boolean;
  signInWithPassword: (email: string, password: string) => Promise<{ error: string | null }>;
  signUpWithPassword: (
    email: string,
    password: string,
    displayName: string,
  ) => Promise<{ error: string | null; needsConfirmation: boolean }>;
  signInWithGoogle: () => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  // undefined = nothing resolved yet this page load; null = anonymous.
  const lastUserIdRef = useRef<string | null | undefined>(undefined);

  // Keeps the demo/local Redux store consistent with who is signed in:
  // logout and switching to a real account both clear demo state, so demo
  // activity can never surface in a real user's session.
  function reconcileDemoState(nextUser: User | null) {
    const uid = nextUser?.id ?? null;
    const prev = lastUserIdRef.current;
    if (prev === uid) return;
    lastUserIdRef.current = uid;

    if (!nextUser) {
      // A user just logged out. The initial anonymous page load (prev ===
      // undefined) keeps any persisted local playground data instead.
      if (prev !== undefined && prev !== null) store.dispatch(resetDemoData());
      return;
    }
    if (isDemoUser(nextUser)) {
      store.dispatch(demoSessionStarted(new Date().toISOString()));
      return;
    }
    // A real account is active: make sure no demo-session data lingers.
    store.dispatch(resetDemoData());
  }

  useEffect(() => {
    const { data: sub } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ?? null);
      reconcileDemoState(newSession?.user ?? null);

      if (newSession?.user) {
        setTimeout(() => loadProfile(newSession.user.id), 0);
      } else {
        setProfile(null);
      }
    });

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setUser(data.session?.user ?? null);
      reconcileDemoState(data.session?.user ?? null);

      if (data.session?.user) {
        loadProfile(data.session.user.id);
      }

      setLoading(false);
    });

    return () => sub.subscription.unsubscribe();
  }, []);

  async function loadProfile(userId: string) {
    const { data } = await supabase
      .from("profiles")
      .select("id, display_name, plan, plan_selected_at, avatar_url")
      .eq("id", userId)
      .maybeSingle();

    if (data) {
      setProfile(data as Profile);
    }
  }

  const refreshProfile = async () => {
    const { data } = await supabase.auth.getSession();
    const uid = data.session?.user?.id;
    if (uid) await loadProfile(uid);
  };

  const signInWithPassword: AuthContextValue["signInWithPassword"] = async (email, password) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    return { error: error?.message ?? null };
  };

  const signUpWithPassword: AuthContextValue["signUpWithPassword"] = async (
    email,
    password,
    displayName,
  ) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/auth`,
        data: {
          display_name: displayName,
        },
      },
    });

    return {
      error: error?.message ?? null,
      // When email confirmation is required, signUp returns a user but no session.
      needsConfirmation: !error && !!data.user && !data.session,
    };
  };

  const signInWithGoogle: AuthContextValue["signInWithGoogle"] = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth`,
      },
    });

    return {
      error: error?.message ?? null,
    };
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    setProfile(null);
  };

  return (
    <AuthContext.Provider
      value={{
        session,
        user,
        profile,
        loading,
        signInWithPassword,
        signUpWithPassword,
        signInWithGoogle,
        signOut,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);

  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return ctx;
}
