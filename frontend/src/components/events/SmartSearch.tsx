import { Search } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

const EXAMPLES = [
  "Free hackathons this weekend",
  "Cyber security workshop under ₹300",
  "AI events this Saturday",
  "Online webinars next week",
  "Internships",
];

/** One search bar: type a sentence, press Enter. Opens /search, which shows what it understood. */
export function SmartSearch({ initial = "", className = "", onSearch }: { initial?: string; className?: string; onSearch?: (q: string) => void }) {
  const navigate = useNavigate();
  const [text, setText] = useState(initial);
  const [i, setI] = useState(0);
  useEffect(() => setText(initial), [initial]);
  useEffect(() => {
    if (text) return;
    const t = window.setInterval(() => setI((n) => (n + 1) % EXAMPLES.length), 3500);
    return () => window.clearInterval(t);
  }, [text]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = text.trim();
    if (!q) return;
    if (onSearch) onSearch(q);
    else navigate(`/search?q=${encodeURIComponent(q)}`);
  };

  return (
    <form role="search" onSubmit={submit} className={`flex gap-2 ${className}`}>
      <label className="relative flex-1">
        <span className="sr-only">Describe the event you want</span>
        <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-text-2" aria-hidden />
        <input
          type="search"
          enterKeyHint="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={200}
          placeholder={`Try "${EXAMPLES[i]}"`}
          className="h-12 w-full rounded-[14px] bg-surface pl-11 pr-4 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]"
        />
      </label>
      <button type="submit" aria-label="Search" className="pressable grid size-12 shrink-0 place-items-center rounded-[14px] bg-accent-fill text-white">
        <Search className="size-5" aria-hidden />
      </button>
    </form>
  );
}
