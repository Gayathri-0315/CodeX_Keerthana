import { m } from "motion/react";
import { ArrowRight, BellRing, CalendarDays, ScanLine } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CategoryGrid, CategoryGridSkeleton } from "../components/landing/CategoryGrid";
import { PublicEventCard, PublicEventCardSkeleton } from "../components/landing/PublicEventCard";
import { SmartSearch } from "../components/events/SmartSearch";
import { OpportunityTabs, typeParam, type TypeTab } from "../components/events/OpportunityTabs";
import { Button } from "../components/ui/Button";
import { openAuth, showRoleNotice } from "../lib/authModal";
import { easeOut } from "../lib/motion";
import { useCategories, useHappeningSoon, useMe } from "../lib/queries";

const rise = (delay = 0) => ({
  initial: { opacity: 0, y: 8 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-40px" },
  transition: { duration: 0.25, ease: easeOut, delay },
});

/** The public first page: what ShowUp is, events happening soon, and categories to browse. */
export default function Landing() {
  const { data: me } = useMe();
  const { hash } = useLocation();
  const navigate = useNavigate();
  const [type, setType] = useState<TypeTab>("all");
  const soon = useHappeningSoon(8, typeParam(type));
  const categories = useCategories();

  // Arriving with #categories (from the nav) scrolls once the cards are there.
  useEffect(() => {
    if (hash === "#categories" && categories.data) document.getElementById("categories")?.scrollIntoView({ behavior: "smooth" });
  }, [hash, categories.data]);

  const createEvent = () => {
    if (me?.role === "organizer") navigate("/organizer/new");
    else if (me) showRoleNotice("student_needs_organizer");
    else openAuth({ audience: "organizer", mode: "signup", intent: { kind: "create_event" } });
  };

  return (
    <div className="flex flex-col gap-16 pb-4 md:gap-24">
      {/* 1. Hero */}
      <section className="grid items-center gap-10 pt-4 md:grid-cols-[1.15fr_1fr] md:pt-10">
        <div>
          <h1 className="text-[40px] font-semibold leading-[1.05] tracking-[-0.03em] sm:text-[52px]">Events that fit your week.</h1>
          <p className="body mt-4 max-w-[38ch] text-text-2">ShowUp shows only the events you can actually make, then helps you get there.</p>
          <SmartSearch className="mt-6 max-w-[520px]" />
          <div className="mt-7 flex flex-wrap gap-3">
            <Link to="/explore" className="pressable inline-flex h-[52px] items-center gap-2 rounded-[14px] bg-accent-fill px-6 text-[17px] font-semibold text-white">
              Explore events <ArrowRight className="size-5" aria-hidden />
            </Link>
            <Button size="lg" variant="secondary" onClick={createEvent}>Create an event</Button>
          </div>
        </div>
        <HeroVisual />
      </section>

      {/* 2. Opportunity tabs, then 3. Happening soon */}
      <section aria-labelledby="soon-title">
        <OpportunityTabs value={type} onChange={setType} className="mb-6" />
        <div className="mb-5 flex items-end justify-between gap-4">
          <h2 id="soon-title" className="title-2">{type === "internship" ? "Open internships" : "Happening soon"}</h2>
          <Link to="/explore" className="inline-flex min-h-11 items-center gap-1 callout font-medium text-accent">See all <ArrowRight className="size-4" aria-hidden /></Link>
        </div>
        {soon.isError ? (
          <div className="card p-6 text-center">
            <p className="headline">Couldn't load events.</p>
            <Button variant="secondary" className="mt-4" onClick={() => soon.refetch()}>Try again</Button>
          </div>
        ) : soon.isPending ? (
          <div className="grid gap-3 md:grid-cols-2">{Array.from({ length: 4 }, (_, i) => <PublicEventCardSkeleton key={i} />)}</div>
        ) : soon.data.length === 0 ? (
          <div className="card p-8 text-center">
            <p className="headline">{type === "all" ? "No upcoming events yet." : "Nothing of this type right now."}</p>
            <p className="callout mt-1 text-text-2">Organizers are adding new ones. Run a club? Be the first.</p>
            <Button className="mt-4" onClick={createEvent}>Create an event</Button>
          </div>
        ) : (
          <ul className={`grid gap-3 transition-opacity md:grid-cols-2 ${soon.isPlaceholderData ? "opacity-60" : ""}`}>
            {soon.data.map((e, i) => (
              <m.li key={e.id} {...rise(Math.min(i, 8) * 0.03)}>
                <PublicEventCard event={e} />
              </m.li>
            ))}
          </ul>
        )}
      </section>

      {/* 3. Browse by category */}
      <section id="categories" aria-labelledby="cat-title" className="scroll-mt-20">
        <h2 id="cat-title" className="title-2 mb-5">Browse by category</h2>
        {categories.isError ? (
          <div className="card p-6 text-center">
            <p className="headline">Couldn't load categories.</p>
            <Button variant="secondary" className="mt-4" onClick={() => categories.refetch()}>Try again</Button>
          </div>
        ) : categories.isPending ? (
          <CategoryGridSkeleton />
        ) : (
          <CategoryGrid categories={categories.data} />
        )}
      </section>

      {/* 4. How it works */}
      <section aria-labelledby="how-title">
        <h2 id="how-title" className="title-2 mb-5">How ShowUp works</h2>
        <ol className="grid gap-3 md:grid-cols-3">
          {[
            { icon: ScanLine, title: "Upload your timetable", body: "Or tap your free hours. We find the gaps in your week." },
            { icon: CalendarDays, title: "See events you can attend", body: "Only events that fit your time, travel and budget." },
            { icon: BellRing, title: "Get reminded and show up", body: "A leave-by alert, and one tap if you can't make it." },
          ].map((s, i) => (
            <m.li key={s.title} {...rise(i * 0.05)} className="card p-5">
              <span className="grid size-11 place-items-center rounded-[14px] bg-accent-soft text-accent">
                <s.icon className="size-6" aria-hidden />
              </span>
              <p className="footnote mt-4 font-semibold text-text-2 tnum">Step {i + 1}</p>
              <h3 className="headline mt-0.5">{s.title}</h3>
              <p className="callout mt-1 text-text-2">{s.body}</p>
            </m.li>
          ))}
        </ol>
      </section>

    </div>
  );
}

/** A tiny free-time grid filling in green next to a card that fits the Saturday gap (CSS keyframes). */
function HeroVisual() {
  const days = ["M", "T", "W", "T", "F", "S", "S"];
  const free = new Set(["5:2", "5:3", "5:4", "6:0", "6:1", "4:4", "2:4"]);
  return (
    <div className="relative mx-auto w-full max-w-[380px]" aria-hidden>
      <div className="card p-5">
        <div className="grid grid-cols-7 gap-1.5">
          {days.map((d, i) => <span key={i} className="footnote text-center font-semibold text-text-2">{d}</span>)}
          {Array.from({ length: 5 * 7 }, (_, k) => {
            const row = Math.floor(k / 7);
            const day = k % 7;
            const isFree = free.has(`${day}:${row}`);
            return (
              <span
                key={k}
                className="hero-cell h-7"
                data-free={isFree ? "" : undefined}
                style={isFree ? { animationDelay: `${day * 0.08 + row * 0.04}s` } : undefined}
              />
            );
          })}
        </div>
      </div>
      <div className="hero-fit card absolute -bottom-8 -right-2 w-[78%] p-4 sm:-right-6">
        <p className="footnote font-semibold text-success-text">Fits your Saturday gap</p>
        <p className="headline mt-0.5">AI Workshop</p>
        <p className="footnote text-text-2 tnum">Sat, 3 to 5 PM · ₹100</p>
      </div>
    </div>
  );
}
