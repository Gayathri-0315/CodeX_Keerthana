import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { openAuth, showRoleNotice } from "../../lib/authModal";
import { useMe } from "../../lib/queries";
import { Button } from "../ui/Button";
import { useToast } from "../ui/Toaster";

type ClubHit = {
  slug: string; name: string; logo_url: string | null; city: string | null; college_or_company: string | null;
  trust_label: string | null; followers: number; following: boolean;
};

/** Clubs whose name matches the search, each with Follow. Nothing shows when no club matches. */
export function ClubResults({ q }: { q: string }) {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const key = ["club-search", q, me?.id ?? null];
  const { data } = useQuery({
    queryKey: key,
    queryFn: () => api<{ items: ClubHit[] }>(`/public/clubs?q=${encodeURIComponent(q)}`).then((r) => r.items),
    enabled: !!q.trim(),
    staleTime: 30_000,
  });
  const follow = useMutation({
    mutationFn: ({ slug, on }: { slug: string; on: boolean }) =>
      api<{ following: boolean; followers: number }>(`/clubs/${slug}/follow`, { method: on ? "POST" : "DELETE" }),
    onMutate: ({ slug, on }) => {
      const prev = qc.getQueryData<ClubHit[]>(key);
      qc.setQueryData<ClubHit[]>(key, (l) => l?.map((c) => (c.slug === slug ? { ...c, following: on, followers: c.followers + (on ? 1 : -1) } : c)));
      return { prev };
    },
    onError: (e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
      toast({ tone: "error", title: "That didn't work", body: (e as Error).message });
    },
    onSuccess: (r, { slug }) => {
      qc.setQueryData<ClubHit[]>(key, (l) => l?.map((c) => (c.slug === slug ? { ...c, ...r } : c)));
      qc.invalidateQueries({ queryKey: ["club", slug] });
      qc.invalidateQueries({ queryKey: ["me", "following"] });
    },
  });

  if (!data?.length) return null;
  const onFollow = (c: ClubHit) => {
    if (!me) return openAuth({ audience: "student", intent: { kind: "follow", slug: c.slug } });
    if (me.role !== "student") return showRoleNotice("organizer_cannot_register");
    follow.mutate({ slug: c.slug, on: !c.following });
  };

  return (
    <section className="mb-6" aria-labelledby="club-results">
      <h2 id="club-results" className="headline mb-2">Clubs</h2>
      <ul className="card divide-y divide-line px-4">
        {data.map((c) => {
          const meta = [c.trust_label, c.college_or_company || c.city, c.followers === 1 ? "1 follower" : `${c.followers} followers`].filter(Boolean).join(" · ");
          return (
            <li key={c.slug} className="flex items-center gap-3 py-3">
              <Link to={`/club/${c.slug}`} className="pressable flex min-w-0 flex-1 items-center gap-3">
                <span className="grid size-10 shrink-0 place-items-center overflow-hidden rounded-[12px] bg-accent-soft text-accent">
                  {c.logo_url ? <img src={c.logo_url} alt="" width={40} height={40} className="size-full object-cover" /> : <span className="headline">{c.name[0]}</span>}
                </span>
                <span className="min-w-0">
                  <span className="body block truncate font-medium">{c.name}</span>
                  <span className="footnote block truncate text-text-2 tnum">{meta}</span>
                </span>
              </Link>
              <Button size="sm" variant={c.following ? "secondary" : "primary"} aria-pressed={c.following} onClick={() => onFollow(c)} className="shrink-0">
                {c.following ? "Following" : "Follow"}
              </Button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
