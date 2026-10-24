import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LazyMotion, MotionConfig } from "motion/react";
import { lazy, Suspense, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { Toaster } from "../components/ui/Toaster";
import { ApiError } from "../lib/api";
import { useMe } from "../lib/queries";

const Welcome = lazy(() => import("../pages/Welcome"));
const SignIn = lazy(() => import("../pages/SignIn"));
const Home = lazy(() => import("../pages/Home"));
const CalendarPage = lazy(() => import("../pages/CalendarPage"));
const MyEvents = lazy(() => import("../pages/MyEvents"));
const Alerts = lazy(() => import("../pages/Alerts"));
const Settings = lazy(() => import("../pages/Settings"));
const RoleHome = lazy(() => import("../pages/RoleHome"));
const EventPage = lazy(() => import("../pages/EventPage"));

const loadFeatures = () => import("./features").then((r) => r.default);

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

/** Signed-in only. Students finish onboarding first (the calendar is part of onboarding). */
function RequireAuth({ children }: { children: ReactNode }) {
  const { data: me, isPending, isError, refetch } = useMe();
  const { pathname } = useLocation();
  if (isPending) return <Splash />;
  if (isError) {
    return (
      <div className="grid min-h-dvh place-items-center p-6 text-center">
        <div>
          <p className="headline">Can't reach ShowUp right now.</p>
          <p className="callout mt-1 text-text-2">Check your connection, then try again.</p>
          <button className="pressable mt-4 min-h-11 rounded-full bg-accent px-5 font-semibold text-white" onClick={() => refetch()}>
            Try again
          </button>
        </div>
      </div>
    );
  }
  if (!me) return <Navigate to="/welcome" replace />;
  if (me.role === "student" && !me.onboarded && pathname !== "/calendar") return <Navigate to="/welcome" replace />;
  return <>{children}</>;
}

function HomeForRole() {
  const { data: me } = useMe();
  return me && me.role !== "student" ? <RoleHome /> : <Home />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LazyMotion features={loadFeatures} strict>
        <MotionConfig reducedMotion="user">
          <Toaster>
            <BrowserRouter>
              <Suspense fallback={<Splash />}>
                <Routes>
                  <Route path="/welcome" element={<Welcome />} />
                  <Route path="/signin" element={<SignIn />} />
                  <Route
                    element={
                      <RequireAuth>
                        <AppShell />
                      </RequireAuth>
                    }
                  >
                    <Route index element={<HomeForRole />} />
                    <Route path="calendar" element={<CalendarPage />} />
                    <Route path="my" element={<MyEvents />} />
                    <Route path="alerts" element={<Alerts />} />
                    <Route path="settings" element={<Settings />} />
                    <Route path="event/:id" element={<EventPage />} />
                  </Route>
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Suspense>
            </BrowserRouter>
          </Toaster>
        </MotionConfig>
      </LazyMotion>
    </QueryClientProvider>
  );
}
