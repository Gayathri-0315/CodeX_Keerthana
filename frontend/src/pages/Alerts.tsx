import { Bell } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/AppShell";

export default function Alerts() {
  return (
    <>
      <PageHeader title="Alerts" />
      <div className="card p-8 text-center">
        <Bell className="mx-auto size-10 text-text-2" aria-hidden />
        <p className="headline mt-3">You're all caught up.</p>
        <p className="callout mt-1 text-text-2">We'll tell you when an event fits your week. At most a few a week.</p>
        <Link to="/settings" className="pressable mt-4 inline-flex min-h-11 items-center rounded-[14px] bg-accent-soft px-5 font-semibold text-accent">
          Alert settings
        </Link>
      </div>
    </>
  );
}
