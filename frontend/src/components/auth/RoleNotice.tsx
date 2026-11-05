import { closeRoleNotice, openAuth, useRoleNotice } from "../../lib/authModal";
import { useSignOut } from "../../lib/queries";
import { Button } from "../ui/Button";
import { Sheet } from "../ui/Sheet";

const COPY = {
  student_needs_organizer: {
    title: "You're signed in as a student",
    body: "To create events, sign in with an organizer account.",
    next: "organizer" as const,
  },
  organizer_cannot_register: {
    title: "You're signed in as an organizer",
    body: "Organizers can't register for events. To register, sign in with a student account.",
    next: "student" as const,
  },
};

/** Shown instead of the sign-in popup when a signed-in person taps an action meant for the other role. */
export function RoleNotice() {
  const notice = useRoleNotice();
  const signOut = useSignOut();
  const copy = notice ? COPY[notice] : null;
  return (
    <Sheet open={!!copy} onClose={closeRoleNotice} title={copy?.title ?? ""}>
      <p className="callout text-text-2">{copy?.body}</p>
      <div className="mt-6 flex flex-col gap-2">
        <Button
          size="lg"
          full
          loading={signOut.isPending}
          onClick={() =>
            signOut.mutate(undefined, {
              onSuccess: () => {
                const next = copy!.next;
                closeRoleNotice();
                openAuth({ audience: next, intent: next === "organizer" ? { kind: "create_event" } : null });
              },
            })
          }
        >
          Sign out
        </Button>
        <Button variant="quiet" size="lg" full onClick={closeRoleNotice}>Cancel</Button>
      </div>
    </Sheet>
  );
}
