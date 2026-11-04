import { Link } from "react-router-dom";

/** Set VITE_CONTACT_EMAIL at build time (see README). Hidden until it is set. */
export const CONTACT_EMAIL: string = import.meta.env.VITE_CONTACT_EMAIL ?? "";

/** Terms, Privacy, Cookies and contact: the quiet footer row used on public screens and in Settings. */
export function LegalLinks({ className = "" }: { className?: string }) {
  const link = "inline-flex min-h-11 items-center underline-offset-4 hover:underline";
  return (
    <nav aria-label="Legal" className={`flex flex-wrap gap-x-4 footnote text-text-2 ${className}`}>
      <Link to="/terms" className={link}>Terms</Link>
      <Link to="/privacy" className={link}>Privacy</Link>
      <Link to="/cookies" className={link}>Cookies</Link>
      {CONTACT_EMAIL && <a href={`mailto:${CONTACT_EMAIL}`} className={link}>{CONTACT_EMAIL}</a>}
    </nav>
  );
}
