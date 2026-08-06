// Auth context, ported from ../nafa-iq-zenith/src/hooks/use-auth.tsx and adapted
// for React Native: AsyncStorage-backed session, Google OAuth via an Expo
// deep-link flow (expo-web-browser), and no web-only debug logging.
import type { Session, User } from "@supabase/supabase-js";
import { makeRedirectUri } from "expo-auth-session";
import * as QueryParams from "expo-auth-session/build/QueryParams";
import * as WebBrowser from "expo-web-browser";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { supabase } from "@/lib/supabase";

WebBrowser.maybeCompleteAuthSession();

export type Profile = {
  id: string;
  display_name: string | null;
  plan: string;
  plan_selected_at: string | null;
  avatar_url: string | null;
};

type Result = { error: string | null; needsConfirmation?: boolean };

type AuthContextValue = {
  session: Session | null;
  user: User | null;
  profile: Profile | null;
  loading: boolean;
  signInWithPassword: (email: string, password: string) => Promise<Result>;
  signUpWithPassword: (email: string, password: string, displayName: string) => Promise<Result>;
  signInWithGoogle: () => Promise<Result>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// Deep link the OAuth provider redirects back to (app.json scheme: nafaiqmobile).
const redirectTo = makeRedirectUri({ scheme: "nafaiqmobile", path: "auth/callback" });

/** Establish a Supabase session from the OAuth redirect URL (PKCE or implicit). */
/** Fetch the user's profile row (or null). Module-level so it stays stable. */
async function fetchProfile(userId: string): Promise<Profile | null> {
  const { data } = await supabase
    .from("profiles")
    .select("id, display_name, plan, plan_selected_at, avatar_url")
    .eq("id", userId)
    .maybeSingle();
  return (data as Profile) ?? null;
}

async function sessionFromUrl(url: string): Promise<Result> {
  const { params, errorCode } = QueryParams.getQueryParams(url);
  if (errorCode) return { error: errorCode };

  if (params.code) {
    const { error } = await supabase.auth.exchangeCodeForSession(params.code);
    return { error: error?.message ?? null };
  }
  const { access_token, refresh_token } = params;
  if (!access_token) return { error: "No session returned from provider" };
  const { error } = await supabase.auth.setSession({ access_token, refresh_token });
  return { error: error?.message ?? null };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const { data: sub } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ?? null);
      if (newSession?.user) {
        // Defer to avoid the known onAuthStateChange deadlock.
        setTimeout(() => {
          fetchProfile(newSession.user.id).then((p) => p && setProfile(p));
        }, 0);
      } else {
        setProfile(null);
      }
    });

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setUser(data.session?.user ?? null);
      if (data.session?.user) {
        fetchProfile(data.session.user.id).then((p) => p && setProfile(p));
      }
      setLoading(false);
    });

    return () => sub.subscription.unsubscribe();
  }, []);

  const signInWithPassword: AuthContextValue["signInWithPassword"] = async (email, password) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
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
      options: { emailRedirectTo: redirectTo, data: { display_name: displayName } },
    });
    return { error: error?.message ?? null, needsConfirmation: !error && data.session == null };
  };

  const signInWithGoogle: AuthContextValue["signInWithGoogle"] = async () => {
    // Must be listed EXACTLY in Supabase Dashboard > Auth > URL Configuration >
    // Redirect URLs, or Supabase silently falls back to the Site URL (web app).
    if (__DEV__) console.log("[auth] Google redirectTo:", redirectTo);
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo, skipBrowserRedirect: true },
    });
    if (error) return { error: error.message };
    if (!data?.url) return { error: "Could not start Google sign-in" };
    if (__DEV__) console.log("[auth] authorize URL:", data.url);

    const res = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
    if (res.type === "cancel" || res.type === "dismiss") return { error: null };
    if (res.type !== "success") return { error: "Google sign-in was interrupted" };
    return sessionFromUrl(res.url);
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    setProfile(null);
  };

  // Re-fetch the profile row (e.g. after a plan change) — mirrors web.
  const refreshProfile = async () => {
    const { data } = await supabase.auth.getSession();
    const uid = data.session?.user?.id;
    if (!uid) return;
    const p = await fetchProfile(uid);
    if (p) setProfile(p);
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
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
