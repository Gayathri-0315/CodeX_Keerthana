import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Globe, Mail } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PublicEventCard } from "../components/landing/PublicEventCard";
import { Button } from "../components/ui/Button";
import { Tag } from "../components/ui/Chip";
import { useToast } from "../components/ui/Toaster";
import { api, ApiError } from "../lib/api";
import { openAuth, showRoleNotice } from "../lib/authModal";
import { formatDayTime } from "../lib/format";
import { useMe } from "../lib/queries";
import type { FeedItem } from "../lib/types";

type ClubEvent = { id: string; title: string; start_at: string; end_at: string; event_type: string; category_slug: string | null; mode: string;
  venue_name: string | null; fee_inr: number; poster_url: string | null; category: string };
type Club = {
  slug: string; name: string; logo_url: string | null; bio: string | null; org_type: string | null; college_or_company: string | null;
  city: string | null; trust_level: "new" | "verified" | "trusted"; trust_label: string | null; website: string | null; instagram: string | null;
  linkedin: string | null; contact_email: string | null; followers: number; following: boolean; events_hosted: number | null;
  attendance_rate: number | null; upcoming: ClubEvent[]; past: ClubEvent[];
};

// No organizer name on these cards: the whole page is that club.
const asCard = (e: ClubEvent): FeedItem => ({ ...e, organizer_name: null, guest: true } as unknown as FeedItem);

/** Public club page: who they are, follow, and their upcoming and past events. */
export default function ClubPage() {
  const { slug = "" } = useParams();
  const { data: me } = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const [showPast, setShowPast] = useState(false);
  const { data: club, isPending, error } = useQuery({ queryKey: ["club", slug], queryFn: () => api<Club>(`/public/clubs/${slug}`) });
  const follow = useMutation({
    mutationFn: (on: boolean) => api<{ following: boolean; followers: number }>(`/clubs/${slug}/follow`, { method: on ? "POST" : "DELETE" }),
    onMutate: async (on) => {
      const prev = qc.getQueryData<Club>(["club", slug]);
      if (prev) qc.setQueryData(["club", slug], { ...prev, following: on, followers: prev.followers + (on ? 1 : -1) });
      return { prev };
    },
    onError: (e, _on, ctx) => {
      if (ctx?.prev) qc.setQueryData(["club", slug], ctx.prev);
      toast({ tone: "error", title: "That didn't work", body: (e as Error).message });
    },
    onSuccess: (r) => qc.setQueryData<Club>(["club", slug], (c) => (c ? { ...c, ...r } : c)),
  });

  if (isPending) return <div className="mx-auto max-w-2xl" aria-busy="true"><div className="skeleton h-40 rounded-[22px]" /></div>;
  if (error || !club) {
    const missing = error instanceof ApiError && error.status === 404;
    return (
      <div className="card mx-auto mt-8 max-w-md p-8 text-center">
        <p className="title-3">{missing ? "This club doesn't exist." : "Couldn't load this club."}</p>
        <Link to="/explore" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-fill px-5 font-semibold text-white">Explore events</Link>
      </div>
    );
  }

  const onFollow = () => {
    if (!me) return openAuth({ audience: "student", intent: { kind: "follow", slug } });
    if (me.role !== "student") return showRoleNotice("organizer_cannot_register");
    follow.mutate(!club.following);
  };
  const meta = [club.college_or_company, club.city].filter(Boolean).join(" · ");
  const links = [{ href: club.website, label: "Website" }, { href: club.instagram, label: "Instagram" }, { href: club.linkedin, label: "LinkedIn" }]
    .filter((l): l is { href: string; label: string } => !!l.href);

  return (
    <div className="mx-auto max-w-2xl">
      <header className="flex items-start gap-4">
        <span className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-[18px] bg-accent-soft text-accent">
          {club.logo_url ? <img src={club.logo_url} alt="" width={64} height={64} className="size-full object-cover" /> : <span className="title-2">{club.name[0]}</span>}
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="title-2">{club.name}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            {club.trust_label && <Tag tone={club.trust_level === "new" ? "neutral" : "success"}>{club.trust_label}</Tag>}
            <span className="footnote text-text-2 tnum">{club.followers === 1 ? "1 follower" : `${club.followers} followers`}</span>
          </div>
          {meta && <p className="footnote mt-1 text-text-2">{meta}</p>}
        </div>
      </header>
      {club.bio && <p className="body mt-4 text-text-2">{club.bio}</p>}
      {(links.length > 0 || club.contact_email) && (
        <div className="mt-2 flex flex-wrap gap-x-4">
          {links.map((l) => (
            <a key={l.label} href={l.href} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex min-h-11 items-center gap-1.5 callout font-medium text-accent">
              <Globe className="size-4" aria-hidden />{l.label}
            </a>
          ))}
          {club.contact_email && (
            <a href={`mailto:${club.contact_email}`} className="inline-flex min-h-11 items-center gap-1.5 callout font-medium text-accent">
              <Mail className="size-4" aria-hidden />{club.contact_email}
            </a>
          )}
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button onClick={onFollow} variant={club.following ? "secondary" : "primary"} aria-pressed={club.following}>
          {club.following ? "Following" : "Follow"}
        </Button>
        {club.events_hosted != null && (
          <p className="footnote text-text-2 tnum">
            {club.events_hosted} events hosted{club.attendance_rate != null ? ` · ${Math.round(club.attendance_rate * 100)}% average attendance` : ""}
          </p>
        )}
      </div>

      <section className="mt-8" aria-labelledby="club-upcoming">
        <h2 id="club-upcoming" className="title-3 mb-3">Upcoming</h2>
        {club.upcoming.length === 0 ? (
          <p className="callout text-text-2">No upcoming events right now. Follow to hear when they post one.</p>
        ) : (
          <ul className="grid gap-3">{club.upcoming.map((e) => <li key={e.id}><PublicEventCard event={asCard(e)} /></li>)}</ul>
        )}
      </section>

      {club.past.length > 0 && (
        <section className="mt-8">
          <button onClick={() => setShowPast((v) => !v)} aria-expanded={showPast} className="inline-flex min-h-11 items-center gap-1 headline">
            Past events <ChevronDown className={`size-5 transition-transform duration-200 ${showPast ? "rotate-180" : ""}`} aria-hidden />
          </button>
          {showPast && (
            <ul className="card mt-2 divide-y divide-line px-5">
              {club.past.map((e) => (
                <li key={e.id} className="py-3">
                  <p className="body">{e.title}</p>
                  <p className="footnote text-text-2 tnum">{formatDayTime(e.start_at, e.end_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
