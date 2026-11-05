import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { domMax, LazyMotion, MotionConfig } from "motion/react";
import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { AuthModal } from "../components/auth/AuthModal";
import { RoleNotice } from "../components/auth/RoleNotice";
import { PublicShell } from "../components/PublicShell";
import { openAuth } from "../lib/authModal";
import { ErrorBoundary, NotFound, OfflineBanner, WakeBanner } from "../components/AppStates";
import { Toaster } from "../components/ui/Toaster";
import { ApiError } from "../lib/api";
import { useMe } from "../lib/queries";
import Home from "../pages/Home";

const loadCalendar = () => import("../pages/CalendarPage");
const loadMy = () => import("../pages/MyEvents");
const loadWelcome = () => import("../pages/Welcome");

// Fetch the current screen's chunk alongside the app bundle instead of after the session check.
// (Home, every student's landing screen, is in the main bundle.)
({ "/calendar": loadCalendar, "/my": loadMy, "/welcome": loadWelcome } as Record<string, () => Promise<unknown>>)[
  window.location.pathname
]?.();

const Welcome = lazy(loadWelcome);
const CalendarPage = lazy(loadCalendar);
const MyEvents = lazy(loadMy);
const Alerts = lazy(() => import("../pages/Alerts"));
const Settings = lazy(() => import("../pages/Settings"));
const EventPage = lazy(() => import("../pages/EventPage"));
const OrganizerHome = lazy(() => import("../pages/organizer/OrganizerHome"));
const EventEditor = lazy(() => import("../pages/organizer/EventEditor"));
const ReviewQueue = lazy(() => import("../pages/admin/ReviewQueue"));
const EventManager = lazy(() => import("../pages/organizer/EventManager"));
const Checkin = lazy(() => import("../pages/organizer/Checkin"));
const InvitePage = lazy(() => import("../pages/InvitePage"));
const Landing = lazy(() => import("../pages/Landing"));
const ExplorePage = lazy(() => import("../pages/ExplorePage"));
const CategoryPage = lazy(() => import("../pages/CategoryPage"));
const ClubPage = lazy(() => import("../pages/ClubPage"));
const EventChat = lazy(() => import("../pages/EventChat"));
const ChatsPage = lazy(() => import("../pages/ChatsPage"));
const SearchPage = lazy(() => import("../pages/SearchPage"));
const ForgotPage = lazy(() => import("../pages/AuthPages").then((m) => ({ default: m.ForgotPage })));
const ResetPage = lazy(() => import("../pages/AuthPages").then((m) => ({ default: m.ResetPage })));
const TermsPage = lazy(() => import("../pages/Legal").then((m) => ({ default: m.TermsPage })));
const PrivacyPage = lazy(() => import("../pages/Legal").then((m) => ({ default: m.PrivacyPage })));
const CookiesPage = lazy(() => import("../pages/Legal").then((m) => ({ default: m.CookiesPage })));


const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500 && err.status !== 0) && count < 2,
    },
  },
});

function Splash() {
  return <div className="min-h-dvh bg-bg" aria-busy="true" />;
}

function CantReach({ retry }: { retry: () => void }) {
  return (
    <div className="grid min-h-dvh place-items-center p-6 text-center">
      <div>
        <p className="headline">Can't reach ShowUp right now.</p>
        <p className="callout mt-1 text-text-2">Check your connection, then try again.</p>
        <button className="pressable mt-4 min-h-11 rounded-full bg-accent-fill px-5 font-semibold text-white" onClick={retry}>
          Try again
        </button>
      </div>
    </div>
  );
}

/** Paths a signed-in student must finish onboarding before seeing. Event, explore and category pages stay open. */
const NEEDS_ONBOARDING = ["/", "/my", "/alerts"];

/** Signed-in pages. A guest is sent to the landing page with the sign-in popup, then brought back here. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { data: me, isPending, isError, refetch } = useMe();
  const { pathname, search } = useLocation();
  useEffect(() => {
    if (!isPending && !isError && !me) {
      openAuth({ audience: pathname.startsWith("/organizer") ? "organizer" : "student", intent: { kind: "navigate", to: pathname + search } });
    }
  }, [isPending, isError, me, pathname, search]);
  if (isPending) return <Splash />;
  if (isError) return <CantReach retry={() => refetch()} />;
  if (!me) return <Navigate to="/" replace />;
  if (me.role === "student" && !me.onboarded && NEEDS_ONBOARDING.includes(pathname)) return <Navigate to="/welcome" replace />;
  return <>{children}</>;
}

/** Pages anyone can open: guests get the public layout, signed-in people keep the app shell. */
function EitherShell() {
  const { data: me, isPending, isError, refetch } = useMe();
  if (isPending) return <Splash />;
  if (isError) return <CantReach retry={() => refetch()} />;
  return me ? <AppShell /> : <PublicShell />;
}

/** "/": the landing page for guests; Home for students; the dashboard for organizers. */
function Root() {
  const { data: me } = useMe();
  if (!me) return <Landing />;
  if (me.role === "student" && !me.onboarded) return <Navigate to="/welcome" replace />;
  if (me.role === "organizer") return <OrganizerHome />;
  if (me.role === "admin") return <ReviewQueue />;
  return <Home />;
}

function OnlyRole({ role, children }: { role: "student" | "organizer" | "admin"; children: ReactNode }) {
  const { data: me } = useMe();
  return me?.role === role ? <>{children}</> : <Navigate to="/" replace />;
}

/** Old /signin links (emails, bookmarks): show the landing page with the sign-in popup open. */
function SignInRedirect() {
  useEffect(() => openAuth({ audience: "unknown" }), []);
  return <Navigate to="/" replace />;
}

export function App() {
  return (
    <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      {/* Loaded up front: with async features, m.* elements wait invisible at their initial styles. */}
      <LazyMotion features={domMax} strict>
        <MotionConfig reducedMotion="user">
          <Toaster>
            <OfflineBanner />
            <WakeBanner />
            <BrowserRouter>
              <Suspense fallback={<Splash />}>
                <Routes>
                  <Route path="/welcome" element={<Welcome />} />
                  <Route path="/signin" element={<SignInRedirect />} />
                  <Route path="/invite/:code" element={<InvitePage />} />
                  <Route path="/forgot" element={<ForgotPage />} />
                  <Route path="/reset" element={<ResetPage />} />
                  <Route path="/terms" element={<TermsPage />} />
                  <Route path="/privacy" element={<PrivacyPage />} />
                  <Route path="/cookies" element={<CookiesPage />} />
                  {/* Public pages: guests browse without an account. */}
                  <Route element={<EitherShell />}>
                    <Route index element={<Root />} />
                    <Route path="about" element={<Landing />} />
                    <Route path="explore" element={<ExplorePage />} />
                    <Route path="search" element={<SearchPage />} />
                    <Route path="category/:slug" element={<CategoryPage />} />
                    <Route path="club/:slug" element={<ClubPage />} />
                    <Route path="event/:id" element={<EventPage />} />
                    <Route path="*" element={<NotFound />} />
                  </Route>
                  {/* Signed-in pages. */}
                  <Route
                    element={
                      <RequireAuth>
                        <AppShell />
                      </RequireAuth>
                    }
                  >
                    <Route path="calendar" element={<OnlyRole role="student"><CalendarPage /></OnlyRole>} />
                    <Route path="my" element={<OnlyRole role="student"><MyEvents /></OnlyRole>} />
                    <Route path="alerts" element={<Alerts />} />
                    <Route path="settings" element={<Settings />} />
                    <Route path="event/:id/chat" element={<EventChat />} />
                    <Route path="chats" element={<ChatsPage />} />
                    <Route path="organizer/new" element={<OnlyRole role="organizer"><EventEditor /></OnlyRole>} />
                    <Route path="organizer/event/:id/edit" element={<OnlyRole role="organizer"><EventEditor key="edit" /></OnlyRole>} />
                    <Route path="organizer/event/:id" element={<OnlyRole role="organizer"><EventManager /></OnlyRole>} />
                    <Route path="organizer/event/:id/checkin" element={<OnlyRole role="organizer"><Checkin /></OnlyRole>} />
                  </Route>
                </Routes>
              </Suspense>
              {/* Outside the Suspense boundary: a lazy page loading right after sign-in must not suspend the
                  popup mid-close (that left an invisible layer blocking taps on phones). */}
              <AuthModal />
              <RoleNotice />
            </BrowserRouter>
          </Toaster>
        </MotionConfig>
      </LazyMotion>
    </QueryClientProvider>
    </ErrorBoundary>
  );
}
