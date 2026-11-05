import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { ExploreView } from "../components/events/ExploreView";
import { useCategories, useMe } from "../lib/queries";

const LINES: Record<string, string> = {
  "ai-ml": "Workshops, talks and hackathons on AI and machine learning.",
  "cyber-security": "CTFs, security talks and hands-on hacking labs.",
  "web-app": "Build websites and apps, from first page to launch.",
  data: "Analytics, visualisation and working with real data.",
  cloud: "Cloud platforms, DevOps and deploying what you build.",
  "robotics-iot": "Robots, sensors, drones and connected devices.",
  design: "UI, UX, product design and visual craft.",
  startups: "Pitch nights, founders and building a company.",
  "open-source": "Contribute to open source and meet maintainers.",
  careers: "Placements, internships, resumes and interviews.",
  "cultural-music": "Music, dance, arts and cultural evenings.",
  sports: "Matches, tournaments and staying active.",
  volunteering: "Give time to causes around the city.",
};

/** /category/:slug: big name with emoji, a short line, the count, then that category's events. */
export default function CategoryPage() {
  const { slug = "" } = useParams();
  const { data: categories, isPending } = useCategories();
  const { data: me } = useMe();
  const student = me?.role === "student";
  const cat = categories?.find((c) => c.slug === slug);

  if (isPending) return <div className="skeleton h-28 rounded-[22px]" aria-busy="true" />;
  if (!cat) {
    return (
      <div className="card mx-auto mt-8 max-w-md p-8 text-center">
        <p className="title-3">This category doesn't exist.</p>
        <Link to="/" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">Browse categories</Link>
      </div>
    );
  }
  return (
    <>
      <Link to={{ pathname: me ? "/about" : "/", hash: "#categories" }} className="pressable -ml-2 mb-3 inline-flex min-h-11 items-center gap-1 rounded-full px-2 callout font-medium text-accent">
        <ArrowLeft className="size-5" aria-hidden /> All categories
      </Link>
      <header className="mb-6">
        <h1 className="title-1 flex items-center gap-3"><span className="cat-emoji grid size-11 place-items-center" data-motion="float" aria-hidden>{cat.emoji}</span>{cat.name}</h1>
        {LINES[cat.slug] && <p className="body mt-2 text-text-2">{LINES[cat.slug]}</p>}
        <p className="callout mt-1 text-text-2 tnum">
          {cat.count === 0 ? "No upcoming events yet." : `${cat.count} upcoming ${cat.count === 1 ? "event" : "events"}, soonest first.`}
        </p>
      </header>
      <ExploreView key={slug} category={slug} source={student ? "feed" : "public"} />
    </>
  );
}
