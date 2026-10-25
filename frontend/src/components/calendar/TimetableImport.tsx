import { useQuery } from "@tanstack/react-query";
import { Camera, FileImage } from "lucide-react";
import { useRef, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { ReadingPoster } from "../organizer/PosterDrop";
import { Button } from "../ui/Button";
import { Sheet } from "../ui/Sheet";

export type TimetableResult = {
  timetable: { periods: { day: string; start: string; end: string; label: string | null }[]; confidence: number; notes: string };
  free_slots: { day_of_week: number; start_min: number; end_min: number }[];
  message: string | null;
  source: "live" | "mock" | "cache";
};

const ACCEPT = "image/png,image/jpeg,image/webp,application/pdf";

/** "Import timetable": pick or snap a photo, watch it being read, hand the free gaps back. */
export function TimetableImport({ open, onClose, onResult }: { open: boolean; onClose: () => void; onResult: (r: TimetableResult) => void }) {
  const pick = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);
  const [reading, setReading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const samples = useQuery({
    queryKey: ["timetable-samples"],
    queryFn: () => api<{ timetables: { name: string; title: string; url: string }[] }>("/availability/samples").then((r) => r.timetables),
    staleTime: Infinity,
    enabled: open,
  });

  const run = async (file: File) => {
    if (file.size > 8 * 1024 * 1024) return setError("That file is over 8 MB. Use a smaller photo or PDF.");
    setError(null);
    setReading(file.type === "application/pdf" ? "" : URL.createObjectURL(file));
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await api<TimetableResult>("/availability/timetable", { form });
      if (r.free_slots.length === 0) {
        setError(r.message ?? "We couldn't find any classes in that file. Try a clearer photo, or paint your free time.");
        return;
      }
      onResult(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't read that file. Try again.");
    } finally {
      setReading(null);
    }
  };

  const useSample = async (url: string, name: string) => {
    const blob = await fetch(url).then((r) => r.blob());
    void run(new File([blob], `${name}.png`, { type: "image/png" }));
  };

  const input = (ref: typeof pick, capture?: boolean) => (
    <input
      ref={ref}
      type="file"
      accept={capture ? "image/*" : ACCEPT}
      capture={capture ? "environment" : undefined}
      className="sr-only"
      tabIndex={-1}
      aria-hidden
      onChange={(e) => {
        const f = e.target.files?.[0];
        e.target.value = "";
        if (f) void run(f);
      }}
    />
  );

  return (
    <Sheet open={open} onClose={() => !reading && onClose()} title="Import your timetable">
      {reading !== null ? (
        reading ? (
          <ReadingPoster src={reading} label="Reading your timetable..." alt="Your timetable" />
        ) : (
          <p className="headline py-10 text-center" aria-live="polite">Reading your timetable...</p>
        )
      ) : (
        <>
          <p className="callout text-text-2">We'll mark your class hours as busy and the gaps between 8 AM and 9 PM as free. You can fix anything after.</p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <button onClick={() => camera.current?.click()} className="pressable card flex flex-col items-center gap-2 p-5 callout font-medium">
              <Camera className="size-7 text-accent" aria-hidden /> Take a photo
            </button>
            <button onClick={() => pick.current?.click()} className="pressable card flex flex-col items-center gap-2 p-5 callout font-medium">
              <FileImage className="size-7 text-accent" aria-hidden /> Choose a file
            </button>
          </div>
          {input(camera, true)}
          {input(pick)}
          {error && <p role="alert" className="callout mt-4 text-danger-text">{error}</p>}
          {samples.data && samples.data.length > 0 && (
            <div className="mt-6">
              <p className="footnote mb-2 font-semibold uppercase tracking-wide text-text-2">Or try a sample timetable</p>
              <div className="flex flex-col gap-2">
                {samples.data.map((s) => (
                  <Button key={s.name} variant="secondary" className="justify-start" onClick={() => useSample(s.url, s.name)}>
                    <img src={s.url} alt="" width={48} height={28} className="h-7 w-12 rounded object-cover" /> {s.title}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </Sheet>
  );
}
