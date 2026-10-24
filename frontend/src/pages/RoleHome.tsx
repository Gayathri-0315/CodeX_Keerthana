import { PageHeader } from "../components/AppShell";
import { Tag } from "../components/ui/Chip";
import { useMe } from "../lib/queries";

const TRUST: Record<string, string> = { trusted: "Trusted organizer", verified: "Verified organizer", new: "New organizer" };

/** Landing page for organizers and admins until their tools land (Phase 4). */
export default function RoleHome() {
  const { data: me } = useMe();
  if (!me) return null;
  const org = me.organizer;
  return (
    <>
      <PageHeader title={org ? org.org_name : "Admin"} subtitle={`Signed in as ${me.email}`} />
      <div className="card p-6">
        {org && <Tag tone={org.trust_level === "new" ? "neutral" : "success"}>{TRUST[org.trust_level] ?? org.trust_level}</Tag>}
        <p className="headline mt-3">{org ? "Your organizer dashboard is next." : "The review queue is next."}</p>
        <p className="callout mt-1 text-text-2">
          {org
            ? "Poster upload, trust checks, reach preview and turnout come in the poster-to-listing build."
            : "Approving and rejecting flagged events comes in the poster-to-listing build."}
        </p>
      </div>
    </>
  );
}
