import { useMutation } from "@tanstack/react-query";
import { MessageCircleQuestion, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";

type Answer = { answer: string; found: boolean; source: "ai" | "rules"; ask: "chat" | "organizer" };
const EXAMPLES = ["Is it free?", "Where is it?", "Who can join?"];

/** Ask about this event. Answers come only from the event's own details; otherwise it says where to ask. */
export function AskEvent({ eventId }: { eventId: string }) {
  const [q, setQ] = useState("");
  const ask = useMutation({ mutationFn: (question: string) => api<Answer>(`/events/${eventId}/ask`, { method: "POST", body: { question } }) });
  const submit = (e?: FormEvent, text = q) => {
    e?.preventDefault();
    const t = text.trim();
    if (t.length >= 2 && !ask.isPending) ask.mutate(t);
  };

  return (
    <section className="mt-8" aria-labelledby="ask-title">
      <h2 id="ask-title" className="title-3 flex items-center gap-2">
        <MessageCircleQuestion className="size-5 text-accent" aria-hidden />Ask about this event
      </h2>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <label className="flex-1">
          <span className="sr-only">Your question</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={200} placeholder="Do I need to bring a laptop?"
            className="h-12 w-full rounded-[14px] bg-surface px-4 body text-text shadow-[inset_0_0_0_1px_var(--line)] outline-none focus:shadow-[inset_0_0_0_2px_var(--accent)]" />
        </label>
        <button type="submit" aria-label="Ask" disabled={q.trim().length < 2 || ask.isPending}
          className="pressable grid size-12 shrink-0 place-items-center rounded-[14px] bg-accent-fill text-white disabled:opacity-45">
          <Send className={`size-5 ${ask.isPending ? "animate-pulse" : ""}`} aria-hidden />
        </button>
      </form>
      {!ask.data && !ask.isPending && !ask.isError && (
        <div className="mt-2 flex flex-wrap gap-2">
          {EXAMPLES.map((x) => (
            <button key={x} onClick={() => { setQ(x); submit(undefined, x); }} className="pressable min-h-9 rounded-full bg-text/6 px-3.5 callout text-text-2">{x}</button>
          ))}
        </div>
      )}
      <div aria-live="polite">
        {ask.isPending && <p className="callout mt-3 text-text-2">Checking the event details...</p>}
        {ask.isError && <p className="callout mt-3 text-danger-text">{(ask.error as Error).message}</p>}
        {ask.data && !ask.isPending && (
          <div className="card mt-3 p-4">
            <p className="body">{ask.data.answer}</p>
            {!ask.data.found &&
              (ask.data.ask === "chat" ? (
                <Link to={`/event/${eventId}/chat`} className="mt-1 inline-flex min-h-11 items-center callout font-medium text-accent">Ask in the group chat</Link>
              ) : (
                <p className="callout mt-1 text-text-2">Ask the organizer using their contact details below.</p>
              ))}
            {ask.data.found && <p className="footnote mt-1.5 text-text-2">From the event details. Check with the organizer if it matters.</p>}
          </div>
        )}
      </div>
    </section>
  );
}
