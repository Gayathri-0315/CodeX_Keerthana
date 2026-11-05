import { Globe, Mail } from "lucide-react";
import type { EventDetail } from "../../lib/types";

const TYPE_LABEL: Record<string, string> = {
  college_club: "College club", department: "Department", company: "Company", community: "Community", independent: "Independent",
};

/** Who runs this event: logo, short bio, links, and the official email only if the organizer chose to show it. */
export function OrganizerCard({ org }: { org: NonNullable<EventDetail["organizer"]> }) {
  const meta = [org.org_type ? TYPE_LABEL[org.org_type] : null, org.college_or_company, org.city].filter(Boolean).join(" · ");
  const links = [
    { href: org.website, label: "Website" },
    { href: org.instagram, label: "Instagram" },
    { href: org.linkedin, label: "LinkedIn" },
  ].filter((l): l is { href: string; label: string } => !!l.href);
  if (!org.bio && !meta && links.length === 0 && !org.contact_email && !org.logo_url) return null;
  return (
    <section className="mt-8">
      <h2 className="title-3">About the organizer</h2>
      <div className="card mt-3 p-5">
        <div className="flex items-center gap-3">
          <span className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-[14px] bg-accent-soft text-accent">
            {org.logo_url ? <img src={org.logo_url} alt="" width={48} height={48} className="size-full object-cover" /> : <span className="headline">{org.name[0]}</span>}
          </span>
          <div className="min-w-0">
            <p className="headline">{org.name}</p>
            <p className="footnote text-text-2">{[org.trust_level !== "new" ? org.trust_label : null, meta].filter(Boolean).join(" · ")}</p>
          </div>
        </div>
        {org.bio && <p className="callout mt-3 text-text-2">{org.bio}</p>}
        {(links.length > 0 || org.contact_email) && (
          <div className="mt-3 flex flex-wrap gap-x-4">
            {links.map((l) => (
              <a key={l.label} href={l.href} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex min-h-11 items-center gap-1.5 callout font-medium text-accent">
                <Globe className="size-4" aria-hidden />{l.label}
              </a>
            ))}
            {org.contact_email && (
              <a href={`mailto:${org.contact_email}`} className="inline-flex min-h-11 items-center gap-1.5 callout font-medium text-accent">
                <Mail className="size-4" aria-hidden />{org.contact_email}
              </a>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
