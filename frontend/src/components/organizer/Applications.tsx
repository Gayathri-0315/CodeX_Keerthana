import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Mail } from "lucide-react";
import { api } from "../../lib/api";

type Applicant = { id: string; name: string; email: string; college: string | null; note: string; link: string | null; status: string; at: string };

/** Internship applications sent on ShowUp, newest first. Reply by email. */
export function Applications({ eventId, title }: { eventId: string; title: string }) {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["applications", eventId],
    queryFn: () => api<{ items: Applicant[] }>(`/organizer/events/${eventId}/applications`).then((r) => r.items),
  });
  return (
    <section className="mt-8">
      <h2 className="title-3 mb-3">Applications{data && data.length > 0 && <span className="text-text-2 tnum"> · {data.length}</span>}</h2>
      {isError ? (
        <div className="card p-6 text-center">
          <p className="headline">Couldn't load applications.</p>
          <button onClick={() => refetch()} className="callout mt-2 min-h-11 font-medium text-accent">Try again</button>
        </div>
      ) : isPending ? (
        <div className="skeleton h-32 rounded-[22px]" />
      ) : data.length === 0 ? (
        <div className="card p-6 text-center">
          <p className="headline">No applications yet</p>
          <p className="callout mt-1 text-text-2">Students apply from the internship page. Each one shows up here and in your alerts.</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {data.map((a) => (
            <li key={a.id} className="card p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="headline">{a.name}</p>
                <span className="footnote text-text-2 tnum">{new Date(a.at).toLocaleDateString([], { day: "numeric", month: "short" })}</span>
              </div>
              {a.college && <p className="footnote text-text-2">{a.college}</p>}
              <p className="body mt-2 whitespace-pre-line">{a.note}</p>
              <div className="mt-2 flex flex-wrap gap-x-4">
                <a href={`mailto:${a.email}?subject=${encodeURIComponent(`Your application: ${title}`)}`}
                  className="inline-flex min-h-11 items-center gap-1.5 callout font-medium text-accent">
                  <Mail className="size-4" aria-hidden />Reply to {a.email}
                </a>
                {a.link && (
                  <a href={a.link} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex min-h-11 items-center gap-1.5 callout font-medium text-accent">
                    <ExternalLink className="size-4" aria-hidden />Portfolio / resume
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
