import { Link } from "react-router-dom";
import type { Category } from "../../lib/queries";

/** Pastel hue and emoji motion per category: different per card, gently staggered. */
const LOOK: Record<string, { h: number; motion: "float" | "wiggle" | "pulse" | "spin" }> = {
  "ai-ml": { h: 212, motion: "float" },
  "cyber-security": { h: 152, motion: "pulse" },
  "web-app": { h: 199, motion: "wiggle" },
  data: { h: 262, motion: "float" },
  cloud: { h: 190, motion: "float" },
  "robotics-iot": { h: 28, motion: "wiggle" },
  design: { h: 322, motion: "spin" },
  startups: { h: 8, motion: "float" },
  "open-source": { h: 130, motion: "spin" },
  careers: { h: 40, motion: "pulse" },
  "cultural-music": { h: 282, motion: "wiggle" },
  sports: { h: 96, motion: "spin" },
  volunteering: { h: 346, motion: "pulse" },
};

export function CategoryGrid({ categories }: { categories: Category[] }) {
  return (
    <ul className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {categories.map((c, i) => {
        const look = LOOK[c.slug] ?? { h: 220, motion: "float" as const };
        return (
          <li key={c.slug}>
            <Link
              to={`/category/${c.slug}`}
              className="cat-card flex min-h-[112px] flex-col justify-between p-4 outline-none focus-visible:ring-2 focus-visible:ring-accent"
              style={{ ["--h" as string]: look.h }}
            >
              <span className="cat-emoji grid size-10 place-items-center text-[30px] leading-none" data-motion={look.motion} style={{ animationDelay: `${(i % 4) * 0.25}s` }} aria-hidden>
                {c.emoji}
              </span>
              <span>
                <span className="headline block">{c.name}</span>
                <span className="footnote block text-text-2 tnum">{c.count === 1 ? "1 event" : `${c.count} events`}</span>
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function CategoryGridSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4" aria-hidden>
      {Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton h-[112px] rounded-[22px]" />)}
    </div>
  );
}
