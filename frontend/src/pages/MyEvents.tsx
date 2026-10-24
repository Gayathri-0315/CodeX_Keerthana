import { Ticket } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/AppShell";

export default function MyEvents() {
  return (
    <>
      <PageHeader title="My events" />
      <div className="card p-8 text-center">
        <Ticket className="mx-auto size-10 text-text-2" aria-hidden />
        <p className="headline mt-3">No events yet.</p>
        <p className="callout mt-1 text-text-2">Events you register for show up here with your pass.</p>
        <Link to="/" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent px-5 font-semibold text-white">
          Find events
        </Link>
      </div>
    </>
  );
}
