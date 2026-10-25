import { ImagePlus } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { useSamplePosters } from "../../lib/organizer";
import { usePublicConfig } from "../../lib/queries";

const ACCEPT = "image/png,image/jpeg,image/webp,application/pdf";
const MAX_BYTES = 8 * 1024 * 1024;

type Props = { onFile: (f: File) => void; onManual: () => void; error?: string | null };

export function PosterDrop({ onFile, onManual, error }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const { data: config } = usePublicConfig();
  const { data: samples } = useSamplePosters();

  const take = (f: File | undefined) => {
    if (!f) return;
    if (!ACCEPT.split(",").includes(f.type)) return setLocalError("Upload a PNG, JPEG, WebP or PDF file.");
    if (f.size > MAX_BYTES) return setLocalError("That file is over 8 MB. Use a smaller image or PDF.");
    setLocalError(null);
    onFile(f);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    take(e.dataTransfer.files[0]);
  };

  const useSample = async (url: string, name: string) => {
    const blob = await fetch(url).then((r) => r.blob());
    take(new File([blob], `${name}.png`, { type: "image/png" }));
  };

  return (
    <div>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={`pressable flex min-h-[320px] w-full flex-col items-center justify-center gap-3 rounded-[22px] border-2 border-dashed p-8 text-center transition-colors ${
          over ? "border-accent bg-accent-soft" : "border-text/15 bg-surface"
        }`}
      >
        <span className="grid size-16 place-items-center rounded-full bg-accent-soft text-accent">
          <ImagePlus className="size-8" aria-hidden />
        </span>
        <span className="title-3">Drop your poster</span>
        <span className="callout max-w-[32ch] text-text-2">We'll read the details for you. PNG, JPEG, WebP or PDF, up to 8 MB.</span>
        <span className="callout mt-1 font-semibold text-accent">Choose a file</span>
      </button>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        aria-label="Poster file"
        onChange={(e) => {
          take(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {(localError || error) && <p role="alert" className="callout mt-3 text-danger-text">{localError ?? error}</p>}
      <div className="mt-4 text-center">
        <button onClick={onManual} className="min-h-11 callout font-medium text-accent">Fill in manually</button>
      </div>

      {config?.demo_mode && samples && samples.length > 0 && (
        <div className="mt-8">
          <p className="footnote mb-2 font-semibold uppercase tracking-wide text-text-2">Or try a sample poster</p>
          <div className="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
            {samples.map((s) => (
              <button key={s.name} onClick={() => useSample(s.url, s.name)} className="pressable liftable w-28 shrink-0 text-left" aria-label={`Use sample poster: ${s.title}`}>
                <img src={s.url} alt="" width={112} height={149} loading="lazy" className="aspect-[3/4] w-28 rounded-[12px] object-cover shadow-card" />
                <span className="footnote mt-1.5 line-clamp-2 block text-text-2">{s.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** An image while the AI reads it: a soft shimmer line sweeping down. */
export function ReadingPoster({ src, label = "Reading your poster...", alt = "Your poster" }: { src: string; label?: string; alt?: string }) {
  return (
    <div className="mx-auto max-w-sm text-center">
      <div className="relative overflow-hidden rounded-[22px] shadow-card">
        <img src={src} alt={alt} className="w-full" />
        <div className="absolute inset-0 bg-white/10" />
        <div
          className="absolute inset-x-0 h-24 animate-[sweep_1.6s_ease-in-out_infinite] bg-gradient-to-b from-transparent via-white/50 to-transparent"
          aria-hidden
        />
      </div>
      <p className="headline mt-5" aria-live="polite">{label}</p>
      <p className="callout text-text-2">This takes a few seconds.</p>
    </div>
  );
}
