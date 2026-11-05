import type { KeyboardEvent, MouseEvent } from "react";
import { useNavigate } from "react-router-dom";

/** The organizer's name on a card; opens the club page without opening the event. */
export function ClubName({ name, slug, className = "" }: { name: string | null | undefined; slug?: string | null; className?: string }) {
  const navigate = useNavigate();
  if (!name) return null;
  if (!slug) return <span className={className}>{name}</span>;
  const go = (e: MouseEvent | KeyboardEvent) => {
    e.preventDefault();
    e.stopPropagation();
    navigate(`/club/${slug}`);
  };
  return (
    <span
      role="link"
      tabIndex={0}
      onClick={go}
      onKeyDown={(e) => (e.key === "Enter" ? go(e) : undefined)}
      className={`cursor-pointer underline-offset-2 hover:underline ${className}`}
    >
      {name}
    </span>
  );
}
