import { m } from "motion/react";
import { Suspense, useRef } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { openAuth } from "../lib/authModal";
import { pageVariants } from "../lib/motion";
import { useMe } from "../lib/queries";
import { Logo } from "./AppShell";
import { LegalLinks } from "./LegalLinks";

/** Top glass nav for public pages: logo, Explore, Categories, and Sign in (or back into the app). */
export function PublicNav() {
  const { data: me } = useMe();
  const { pathname } = useLocation();
  const link = (active: boolean) =>
    `inline-flex min-h-11 items-center whitespace-nowrap rounded-full px-2 callout font-medium transition-colors sm:px-4 ${active ? "text-text" : "text-text-2 hover:text-text"}`;
  return (
    <header className="glass safe-top sticky top-0 z-40 border-b border-line">
      <nav className="mx-auto flex h-14 max-w-[1080px] items-center justify-between gap-2 px-3 sm:px-6" aria-label="Main">
        <Link to={me ? "/about" : "/"} aria-label="ShowUp home" className="shrink-0"><Logo compact /></Link>
        <div className="flex items-center sm:gap-0.5">
          <NavLink to="/explore" className={({ isActive }) => link(isActive)}>Explore</NavLink>
          <Link to={{ pathname: me ? "/about" : "/", hash: "#categories" }} className={link(pathname.startsWith("/category"))}>Categories</Link>
          {me ? (
            <Link to="/" className="pressable ml-1 inline-flex min-h-11 items-center whitespace-nowrap rounded-full bg-accent-fill px-3.5 callout font-semibold text-white sm:px-4">Open app</Link>
          ) : (
            <button onClick={() => openAuth({ audience: "unknown" })} className="pressable ml-1 inline-flex min-h-11 items-center whitespace-nowrap rounded-full bg-accent-fill px-3.5 callout font-semibold text-white sm:px-4">
              Sign in
            </button>
          )}
        </div>
      </nav>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-[1080px] flex-col gap-2 px-4 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <Logo />
        <LegalLinks />
      </div>
    </footer>
  );
}

/** Layout for guests: the landing nav, the page, and the footer. */
export function PublicShell() {
  const { pathname } = useLocation();
  const first = useRef(pathname);
  return (
    <div className="flex min-h-dvh flex-col">
      <PublicNav />
      <main id="main" className="mx-auto w-full max-w-[1080px] flex-1 px-4 pb-16 pt-4 sm:px-6 md:pt-8">
        <Suspense fallback={<div className="h-40" />}>
          <m.div key={pathname} variants={pageVariants} initial={pathname === first.current ? false : "initial"} animate="animate">
            <Outlet />
          </m.div>
        </Suspense>
      </main>
      <PublicFooter />
    </div>
  );
}
