import { PageHeader } from "../components/AppShell";
import { ExploreView } from "../components/events/ExploreView";
import { useMe } from "../lib/queries";

/** /explore: every upcoming event. Students see time-fit badges; guests and organizers see the public list. */
export default function ExplorePage() {
  const { data: me } = useMe();
  return me ? (
    <>
      <PageHeader title="Explore" subtitle="Every upcoming event, soonest first." />
      <ExploreView source={me.role === "student" ? "feed" : "public"} />
    </>
  ) : (
    <>
      <h1 className="title-1 mb-1">Explore</h1>
      <p className="callout mb-6 text-text-2">Every upcoming event, soonest first.</p>
      <ExploreView source="public" />
    </>
  );
}
