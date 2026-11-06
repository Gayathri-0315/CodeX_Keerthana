import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";

type Brief = { headline: string; items: { text: string; path: string; priority: number }[]; source: "ai" | "rules" };

/** Organizers and admins: today's few important things, instead of every alert. Hidden when nothing matters. */
export function BriefCard({ className = "" }: { className?: string }) {
  const { data } = useQuery({ queryKey: ["brief"], queryFn: () => api<Brief>("/me/brief"), staleTime: 5 * 60_000 });
  if (!data || data.items.length === 0) return null;
  return (
    <section className={`card overflow-hidden ${className}`} aria-labelledby="brief-title">
      <div className="flex items-center gap-2 px-5 pb-2 pt-4">
        <Sparkles className="size-4 text-accent" aria-hidden />
        <h2 id="brief-title" className="headline">{data.headline || "Today's brief"}</h2>
      </div>
      <ul className="divide-y divide-line">
        {data.items.map((i) => (
          <li key={i.text}>
            <Link to={i.path} className="pressable flex min-h-12 items-center gap-3 px-5 py-2.5 hover:bg-text/4">
              <span className={`size-2 shrink-0 rounded-full ${i.priority >= 80 ? "bg-danger" : i.priority >= 60 ? "bg-warning" : "bg-text/25"}`} aria-hidden />
              <span className="callout flex-1">{i.text}</span>
              <ChevronRight className="size-4 shrink-0 text-text-2" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
      <p className="footnote px-5 pb-3 pt-1 text-text-2">
        {data.source === "ai" ? "Picked by AI from today's activity. Your alerts still have everything." : "The most important things from today's activity. Your alerts still have everything."}
      </p>
    </section>
  );
}
