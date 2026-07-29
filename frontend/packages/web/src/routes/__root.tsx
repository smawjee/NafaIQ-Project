import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  useRouterState,
  useNavigate,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";
import { Provider } from "react-redux";
import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import { Loader2 } from "lucide-react";

import appCss from "../styles.css?url";
import { reportNafaIQError } from "../lib/errors/reporting";
import { AppShell } from "../components/layout/AppShell";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { LandingThemeProvider } from "@/hooks/use-landing-theme";
import { installGlobalErrorReporting } from "@/lib/telemetry";
import { LearnProvider } from "@/hooks/learn/use-learn";
import { Toaster } from "@/components/ui/sonner";
import { ConfirmProvider } from "@/components/shared/ConfirmDialog";
import { store } from "../store";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportNafaIQError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      {
        name: "viewport",
        content: "width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=5",
      },
      { title: "NafaIQ — PSX Terminal & Personal Finance" },
      {
        name: "description",
        content:
          "Premium Pakistan Stock Exchange dashboard, trading terminal, and AI-powered personal finance manager.",
      },
      { name: "author", content: "NafaIQ" },
      { name: "theme-color", content: "#060d1f" },
      { name: "apple-mobile-web-app-capable", content: "yes" },
      { name: "apple-mobile-web-app-status-bar-style", content: "black-translucent" },
      { name: "apple-mobile-web-app-title", content: "NafaIQ" },
      { name: "mobile-web-app-capable", content: "yes" },
      { property: "og:title", content: "NafaIQ — PSX Terminal & Personal Finance" },
      {
        property: "og:description",
        content: "Bloomberg-grade PSX terminal meets a calm personal finance app.",
      },
      { property: "og:type", content: "website" },
      { property: "og:url", content: "https://nafaiq.vercel.app/" },
      {
        property: "og:image",
        content:
          "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/c9d8cc4f-f72d-4076-a36f-7b6b7cdd4499/id-preview-47fd2b28--4efafbc8-f1a0-40cc-a455-7a1e447a9b45.lovable.app-1781772713629.png",
      },
      {
        name: "twitter:image",
        content:
          "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/c9d8cc4f-f72d-4076-a36f-7b6b7cdd4499/id-preview-47fd2b28--4efafbc8-f1a0-40cc-a455-7a1e447a9b45.lovable.app-1781772713629.png",
      },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "manifest", href: "/manifest.webmanifest" },
      { rel: "apple-touch-icon", href: "/icons/apple-touch-icon.png" },
      { rel: "icon", type: "image/png", href: "/icons/icon-192.png" },
      { rel: "canonical", href: "https://nafaiq.vercel.app/" },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Noto+Naskh+Arabic:wght@400;500;600;700&family=Noto+Nastaliq+Urdu:wght@400;600&display=swap",
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <HeadContent />
        <script
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{var t=localStorage.getItem('nafaiq-landing-theme');if(t==='light'){document.documentElement.classList.add('theme-light');document.documentElement.classList.add('landing-light')}}catch(e){}})()",
          }}
        />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function Spinner() {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-background">
      <Loader2 className="h-6 w-6 animate-spin text-bull" />
    </div>
  );
}

const TARGET_PATHS = new Set([
  "/",
  "/app",
  "/psx",
  "/portfolio",
  "/watchlist",
  "/finance",
  "/ai-insights",
  "/learn",
  "/monetary",
  "/help",
  "/team",
]);

const PUBLIC_APP_ROUTES = new Set([
  "/portfolio",
  "/watchlist",
  "/finance",
  "/ai-insights",
  "/learn",
  "/monetary",
  "/alerts",
  "/settings",
  "/help",
]);



function PageTransition({ routeKey, children }: { routeKey: string; children: ReactNode }) {
  const isTarget = TARGET_PATHS.has(routeKey);

  if (!isTarget) {
    return <>{children}</>;
  }

  return (
    <MotionConfig reducedMotion="user">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={routeKey}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { duration: 0.2, ease: "easeOut" } }}
          exit={{ opacity: 0, transition: { duration: 0.15, ease: "easeOut" } }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </MotionConfig>
  );
}

function AuthGate() {
  const { user, loading } = useAuth();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const isAuthRoute = pathname === "/auth";
  const isLanding = pathname === "/";
  const isPlans = pathname === "/plans";
  const isUrduQa = pathname === "/urdu-qa";
  const isTeam = pathname === "/team";
  const isPsx = pathname.startsWith("/psx") || pathname.startsWith("/stock");
  // Admin routes bring their own chrome (AdminShell) and a second-level
  // authorization guard. They are auth-required (not public), so an anonymous
  // user is still redirected to /auth by the effect below.
  const isAdminRoute = pathname === "/admin" || pathname.startsWith("/admin/");
  const isPublicAppRoute = PUBLIC_APP_ROUTES.has(pathname);
  const isPublic = isAuthRoute || isLanding || isPlans || isUrduQa || isTeam || isPublicAppRoute;

  useEffect(() => {
    if (loading) return;
    if (!user && !isPublic && !isPsx) {
      navigate({ to: "/auth", search: { redirect: pathname } });
    }
  }, [loading, user, isPublic, isPsx, navigate, pathname]);

  // Admin routes render bare (AdminShell + AdminGuard live in the route tree).
  // The redirect effect above sends anonymous users to /auth first.
  if (isAdminRoute) {
    return (
      <>
        <Outlet />
        {loading && <Spinner />}
      </>
    );
  }

  // PSX & public app routes get AppShell without auth requirement
  if (isPsx || isPublicAppRoute) {
    return (
      <>
        <AppShell>
          <PageTransition routeKey={pathname}>
            <Outlet />
          </PageTransition>
        </AppShell>
        {loading && <Spinner />}
      </>
    );
  }

  // Outlet must ALWAYS render so the router keeps its matched route (avoids
  // "Expected to find a match below the root match" during hydration).
  if (isPublic) {
    return (
      <PageTransition routeKey={pathname}>
        <Outlet />
      </PageTransition>
    );
  }

  const blocking = loading || !user;
  return (
    <>
      <AppShell>
        <PageTransition routeKey={pathname}>
          <Outlet />
        </PageTransition>
      </AppShell>
      {blocking && <Spinner />}
    </>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  // Catches what an ErrorBoundary structurally cannot: errors thrown from event
  // handlers, async callbacks and rejected promises.
  useEffect(() => installGlobalErrorReporting(), []);

  return (
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
        <AuthProvider>
          <LearnProvider>
            <LandingThemeProvider>
              <ConfirmProvider>
                <AuthGate />
                <Toaster />
              </ConfirmProvider>
            </LandingThemeProvider>
          </LearnProvider>
        </AuthProvider>
      </QueryClientProvider>
    </Provider>
  );
}
