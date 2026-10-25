import { m } from "motion/react";
import { Bell, CalendarDays, Home, Ticket } from "lucide-react";
import { Suspense, useRef } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { pageVariants, spring } from "../lib/motion";
import { useMe } from "../lib/queries";
import { useNotifications } from "../lib/attendance";
import { LiveAlerts } from "./attendance/LiveAlerts";

const TABS = [
  { to: "/", label: "Home", icon: Home },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/my", label: "My events", icon: Ticket },
  { to: "/alerts", label: "Alerts", icon: Bell },
];
// Organizers and admins have few destinations; they get desktop links and in-page buttons, no tab bar.
const DESKTOP_TABS: Record<string, { to: string; label: string }[]> = {
  student: TABS,
  organizer: [{ to: "/", label: "Dashboard" }, { to: "/organizer/new", label: "New event" }],
  admin: [{ to: "/", label: "Review queue" }],
};

export function Logo() {
  return (
    <span className="inline-flex items-center gap-2 headline">
      <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
        <rect width="32" height="32" rx="9" fill="var(--accent)" />
        <path d="M10 16.5l4 4 8-9" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      ShowUp
    </span>
  );
}

export function Avatar() {
  const { data: me } = useMe();
  return (
    <Link
      to="/settings"
      aria-label="Settings"
      className="pressable grid size-11 place-items-center rounded-full"
    >
      <span className="grid size-9 place-items-center rounded-full bg-accent-soft headline text-accent">
        {me?.name?.[0]?.toUpperCase() ?? "?"}
      </span>
    </Link>
  );
}

export function AppShell() {
  const { pathname } = useLocation();
  const { data: me } = useMe();
  const student = me?.role === "student";
  const firstPath = useRef(pathname);
  const firstScreen = useRef(true);
  if (pathname !== firstPath.current) firstScreen.current = false;
  // Event detail has its own sticky action bar, so the tab bar steps aside there.
  const tabBar = student && !pathname.startsWith("/event/");
  const { data: alerts } = useNotifications(student);
  const unread = alerts?.unread ?? 0;
  const badge = (to: string) =>
    to === "/alerts" && unread > 0 ? (
      <span className="absolute -right-1.5 -top-1 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-danger px-1 text-[11px] font-semibold text-white tnum" aria-label={`${unread} unread`}>
        {unread > 9 ? "9+" : unread}
      </span>
    ) : null;

  return (
    <div className="min-h-dvh">
      <LiveAlerts />
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-full focus:bg-surface focus:px-4 focus:py-2">
        Skip to content
      </a>

      {/* Desktop: top glass nav */}
      <header className="glass safe-top sticky top-0 z-40 hidden border-b border-line md:block">
        <nav className="mx-auto flex h-14 max-w-[1080px] items-center justify-between px-6" aria-label="Main">
          <Link to="/" aria-label="ShowUp home"><Logo /></Link>
          {me && (
            <ul className="flex items-center gap-1">
              {DESKTOP_TABS[me.role].map((t) => {
                const active = t.to === "/" ? pathname === "/" : pathname.startsWith(t.to);
                return (
                  <li key={t.to}>
                    <NavLink to={t.to} className={`relative inline-flex min-h-11 items-center rounded-full px-4 callout font-medium transition-colors ${active ? "text-text" : "text-text-2 hover:text-text"}`}>
                      {active && <m.span layoutId="nav-pill" transition={spring} className="absolute inset-x-1 inset-y-1.5 rounded-full bg-text/6" />}
                      <span className="relative">{t.label}{badge(t.to)}</span>
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          )}
          <Avatar />
        </nav>
      </header>

      <main id="main" className={`mx-auto max-w-[1080px] px-4 pt-4 sm:px-6 md:pt-8 ${tabBar ? "pb-32 md:pb-16" : "pb-16"}`}>
        <Suspense fallback={<div className="h-40" />}>
          {/* The first screen paints at once (it's the LCP); later navigations crossfade in. */}
          <m.div key={pathname} variants={pageVariants} initial={firstScreen.current ? false : "initial"} animate="animate">
            <Outlet />
          </m.div>
        </Suspense>
      </main>

      {/* Phone: bottom tab bar */}
      {tabBar && (
        <nav className="glass safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-line md:hidden" aria-label="Main">
          <ul className="mx-auto grid max-w-md grid-cols-4">
            {TABS.map((t) => {
              const active = t.to === "/" ? pathname === "/" : pathname.startsWith(t.to);
              const Icon = t.icon;
              return (
                <li key={t.to}>
                  <NavLink
                    to={t.to}
                    aria-current={active ? "page" : undefined}
                    className={`pressable flex min-h-[54px] flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${active ? "text-accent" : "text-text-2"}`}
                  >
                    <span className="relative">
                      <Icon className="size-6" strokeWidth={active ? 2.2 : 1.8} aria-hidden />
                      {badge(t.to)}
                    </span>
                    {t.label}
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
    </div>
  );
}

/** Large page title with the settings avatar on phones (desktop has it in the nav). */
export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="title-1">{title}</h1>
        {subtitle && <p className="callout mt-1 text-text-2">{subtitle}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {action}
        <div className="md:hidden"><Avatar /></div>
      </div>
    </div>
  );
}
