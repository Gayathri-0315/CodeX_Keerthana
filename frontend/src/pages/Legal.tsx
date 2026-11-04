import type { ReactNode } from "react";
import { CONTACT_EMAIL, LegalLinks } from "../components/LegalLinks";
import { AuthLayout } from "./AuthPages";

function Doc({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <AuthLayout title={title} subtitle={`Last updated ${updated}`}>
      <div className="flex flex-col gap-6 pb-8 [&_h2]:headline [&_li]:mt-1.5 [&_p]:mt-2 [&_p]:body [&_p]:text-text-2 [&_ul]:mt-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:body [&_ul]:text-text-2">
        {children}
        <section>
          <h2>Questions</h2>
          <p>{CONTACT_EMAIL ? <>Write to <a className="text-accent" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.</> : "Use the contact address shown in the footer."}</p>
        </section>
        <LegalLinks />
      </div>
    </AuthLayout>
  );
}

export function TermsPage() {
  return (
    <Doc title="Terms of use" updated="4 November 2026">
      <section>
        <h2>What ShowUp is</h2>
        <p>ShowUp lists student events and suggests the ones that fit your free time. Organizers run their own events; ShowUp is not the organizer and does not take payments.</p>
      </section>
      <section>
        <h2>Your account</h2>
        <ul>
          <li>Use your real name and an email you can read. Keep your password to yourself.</li>
          <li>Student and organizer accounts are separate. Don't use one to act as the other.</li>
          <li>You can delete your account at any time in Settings, Privacy.</li>
        </ul>
      </section>
      <section>
        <h2>For organizers</h2>
        <ul>
          <li>Only list real events you are allowed to run, with honest details.</li>
          <li>No fees to personal UPI IDs, no "guaranteed job" offers, no misleading internships.</li>
          <li>New organizers' first events are checked by a person before they go live. We can hide or remove any listing.</li>
        </ul>
      </section>
      <section>
        <h2>Things you must not do</h2>
        <ul>
          <li>Spam, scam, harass or impersonate anyone.</li>
          <li>Try to break, overload or get around the security of the service.</li>
          <li>Collect other people's data from ShowUp.</li>
        </ul>
        <p>We may suspend accounts that break these rules.</p>
      </section>
      <section>
        <h2>No guarantees</h2>
        <p>We try to keep listings accurate, but events can change or be cancelled by their organizers. Suggestions, travel times and turnout estimates are planning help, not promises. Check important details with the organizer.</p>
      </section>
    </Doc>
  );
}

export function PrivacyPage() {
  return (
    <Doc title="Privacy policy" updated="4 November 2026">
      <section>
        <h2>The short version</h2>
        <p>We collect only what we need to suggest events you can attend and to help you get there. We don't sell your data and we don't use advertising trackers.</p>
      </section>
      <section>
        <h2>What we collect</h2>
        <ul>
          <li><strong>Account:</strong> name, email, a hashed password (never the password itself) and your college. Organizers also give their organization, an official email and, if they want, a phone number.</li>
          <li><strong>Preferences:</strong> interests, your area (a neighbourhood, not your exact address), travel distance, budget and alert settings.</li>
          <li><strong>Free time:</strong> the free and busy hours on your weekly calendar. If you upload a timetable, the image is read to find your class times and is not kept; we keep the class times so the same image isn't read twice.</li>
          <li><strong>Activity:</strong> events you register for, save, dismiss, report or check in to, and the alerts we send you.</li>
          <li><strong>Visit counting:</strong> when a page opens, the app sends the page path, the time and a random ID kept in a cookie, so we can count visits and unique visitors. We don't store your IP address, we skip known bots, and the ID isn't linked to your account.</li>
          <li><strong>Security:</strong> a count of recent wrong passwords on your account, so we can lock it after repeated attempts.</li>
        </ul>
      </section>
      <section>
        <h2>Who sees what</h2>
        <ul>
          <li>Organizers see the names of people registered for their own events, never anyone else's.</li>
          <li>Other students see only counts (for example "3 classmates going"), never names, unless you invite them to go together.</li>
          <li>A small team of admins can see account data to review events, stop abuse and answer support requests. Their actions are logged.</li>
        </ul>
      </section>
      <section>
        <h2>Services we use</h2>
        <ul>
          <li>Hosting and a database provider, to run the app.</li>
          <li>An email provider, to send verification, password and alert emails.</li>
          <li>An AI provider (Anthropic), only when an organizer uploads a poster or you upload a timetable, to read the image. It isn't used to profile you.</li>
        </ul>
      </section>
      <section>
        <h2>Your choices</h2>
        <ul>
          <li><strong>Download my data</strong> and <strong>Delete my data</strong> are in Settings, Privacy. Deleting removes your account, free time, registrations and alerts.</li>
          <li>You can turn alerts off, pause them, or set quiet hours in Settings.</li>
        </ul>
      </section>
    </Doc>
  );
}

export function CookiesPage() {
  return (
    <Doc title="Cookie notice" updated="4 November 2026">
      <section>
        <h2>Cookies we use</h2>
        <ul>
          <li><strong>showup_session</strong>: keeps you signed in. Needed for the app to work.</li>
          <li><strong>showup_csrf</strong>: protects your account from forged requests from other sites. Needed.</li>
          <li><strong>showup_vid</strong>: a random visitor ID used only to count visits (see the privacy policy). It isn't linked to your account.</li>
        </ul>
        <p>We also remember your light or dark theme choice in your browser's local storage. We don't use advertising or third-party tracking cookies.</p>
      </section>
    </Doc>
  );
}
