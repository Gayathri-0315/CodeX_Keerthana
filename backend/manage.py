"""ShowUp management commands. Run from backend/ (or via the npm scripts at the repo root).

  python manage.py migrate                    Apply database migrations (safe to run any time)
  python manage.py seed_dev                   LOCAL ONLY: wipe the database and load sample data
  python manage.py create_admin --email X     Create an admin account (prompts for a strong password)
  python manage.py load_samples               Add sample clubs and events (live site too; real data stays)
  python manage.py remove_samples             Delete the sample clubs and events again
"""

import argparse
import getpass
import sys


def cmd_migrate(_args) -> None:
    from app.migrate import upgrade

    upgrade()
    print("Database is up to date.")


def cmd_seed_dev(_args) -> None:
    from app.config import settings

    if settings.is_production:
        sys.exit("Refusing to run seed_dev: APP_ENV=production. Production starts with an empty database.")
    from app.seed.seed import dev_password, reset_and_seed

    password, generated = dev_password()
    result = reset_and_seed(password)
    print(f"Loaded {result['users']} sample users and {result['events']} sample events (local development data).")
    print("Sample accounts: asha@example.com (student), club@example.com (organizer), student1..30@example.com.")
    if generated:
        print(f"Their password for this run: {password}   (set SEED_DEV_PASSWORD in .env to choose your own)")
    else:
        print("Their password is your SEED_DEV_PASSWORD.")


def cmd_load_samples(_args) -> None:
    from app.migrate import upgrade
    from app.seed.seed import load_samples

    upgrade()
    r = load_samples()
    print(f"Added {r['events']} sample events from 4 sample clubs, with {r['users'] - 4} sample students.")
    print("Each sample event says so at the top of its description. Remove them any time: python manage.py remove_samples")


def cmd_remove_samples(_args) -> None:
    from app.seed.seed import remove_samples

    r = remove_samples()
    print(f"Removed {r['events']} sample events and {r['users']} sample accounts. Real data is untouched.")


def ask(prompt: str) -> str:
    # Hidden typing in a terminal; plain line reads when input is piped (scripts, CI).
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    line = sys.stdin.readline()
    if not line:
        sys.exit("No password given.")
    return line.rstrip("\r\n")


def cmd_create_admin(args) -> None:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.migrate import upgrade
    from sqlalchemy import func

    from app.models import Event, Organizer, User
    from app.security import hash_password, password_problem

    email = args.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        sys.exit("That doesn't look like an email address.")
    upgrade()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        org = None
        if existing and existing.role != "admin":
            if not args.promote:
                sys.exit(f"That email already belongs to {'an' if existing.role == 'organizer' else 'a'} {existing.role} account. To make that account the admin, "
                         f"run this again with --promote (it stops being a {existing.role} account).")
            org = db.scalar(select(Organizer).where(Organizer.user_id == existing.id))
            if org is not None and db.scalar(select(func.count()).select_from(Event).where(Event.organizer_id == org.id)):
                sys.exit(f"That account runs the club '{org.org_name}', which has events. Making it the admin would leave "
                         "those events without anyone to manage them. Use a separate email for the admin.")
        while True:
            pw = ask("Admin password (at least 12 characters, upper and lower case, a number and a symbol): ")
            if problem := password_problem(pw, strong=True):
                print(problem)
                continue
            if ask("Type it again: ") != pw:
                print("The two passwords don't match. Try again.")
                continue
            break
        if existing and existing.role != "admin":
            was = existing.role
            if org is not None:
                db.delete(org)  # a club profile with no events
            existing.role = "admin"
            existing.onboarded = True
            existing.password_hash = hash_password(pw)
            existing.session_version = (existing.session_version or 0) + 1  # signs it out everywhere
            existing.failed_logins, existing.locked_until = 0, None
            print(f"{email} was {'an' if was == 'organizer' else 'a'} {was} account and is now the admin, with the new password. Sign in again.")
        elif existing:
            existing.password_hash = hash_password(pw)
            existing.session_version = (existing.session_version or 0) + 1
            existing.failed_logins, existing.locked_until = 0, None
            print(f"Updated the password for admin {email}.")
        else:
            db.add(User(email=email, name=args.name, role="admin", password_hash=hash_password(pw), onboarded=True))
            print(f"Created admin {email}.")
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(prog="manage.py", description="ShowUp management commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="Apply database migrations").set_defaults(func=cmd_migrate)
    sub.add_parser("seed_dev", help="LOCAL ONLY: reset the database with sample data").set_defaults(func=cmd_seed_dev)
    sub.add_parser("load_samples", help="Add sample clubs and events (safe on the live site)").set_defaults(func=cmd_load_samples)
    sub.add_parser("remove_samples", help="Delete the sample clubs and events").set_defaults(func=cmd_remove_samples)
    p = sub.add_parser("create_admin", help="Create or reset an admin account")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="Admin")
    p.add_argument("--promote", action="store_true", help="Turn an existing student or organizer account into the admin")
    p.set_defaults(func=cmd_create_admin)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
