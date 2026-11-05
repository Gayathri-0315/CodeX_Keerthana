import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

/** Under an apply / registration link: does it actually open? A warning only; saving is never blocked. */
export function LinkCheck({ url }: { url: string | null }) {
  const [settled, setSettled] = useState<string | null>(null);
  useEffect(() => {
    const u = (url ?? "").trim();
    const t = window.setTimeout(() => setSettled(/^https?:\/\/[^\s/]+\.[^\s]+/i.test(u) ? u : null), 900);
    return () => window.clearTimeout(t);
  }, [url]);
  const { data, isFetching } = useQuery({
    queryKey: ["link-check", settled],
    queryFn: () => api<{ ok: boolean; reason: string | null }>("/organizer/check-link", { method: "POST", body: { url: settled } }),
    enabled: !!settled,
    staleTime: 5 * 60_000,
    retry: false,
  });
  if (!settled) return null;
  if (isFetching && !data) {
    return <p className="footnote mt-1.5 flex items-center gap-1.5 text-text-2" role="status"><Loader2 className="size-3.5 animate-spin" aria-hidden />Checking the link opens...</p>;
  }
  if (!data) return null;
  return data.ok ? (
    <p className="footnote mt-1.5 flex items-center gap-1.5 text-success-text" role="status"><CheckCircle2 className="size-3.5" aria-hidden />Link opens</p>
  ) : (
    <p className="footnote mt-1.5 flex items-start gap-1.5 text-warning-text" role="alert">
      <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
      <span>{data.reason} Students will see an error if they tap it.</span>
    </p>
  );
}
