"""The fixed category list (prompt v2, item 11) and a tag-based suggestion used by poster reading."""

CATEGORIES: list[tuple[str, str, str]] = [  # (slug, name, emoji), in display order
    ("ai-ml", "AI & ML", "🤖"),
    ("cyber-security", "Cyber Security", "🛡️"),
    ("web-app", "Web & App", "💻"),
    ("data", "Data", "📊"),
    ("cloud", "Cloud", "☁️"),
    ("robotics-iot", "Robotics & IoT", "🦾"),
    ("design", "Design", "🎨"),
    ("startups", "Startups", "🚀"),
    ("open-source", "Open Source", "🌍"),
    ("careers", "Careers", "💼"),
    ("cultural-music", "Cultural & Music", "🎵"),
    ("sports", "Sports", "⚽"),
    ("volunteering", "Volunteering", "🤝"),
]
SLUGS = {slug for slug, _, _ in CATEGORIES}

# First matching word wins, so put the most specific words first.
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("cyber-security", ("cybersecurity", "cyber", "security", "ctf", "hacking-ethical")),
    ("ai-ml", ("ai", "ml", "machine-learning", "llm", "deep-learning", "genai")),
    ("robotics-iot", ("robotics", "iot", "embedded", "drone")),
    ("cloud", ("cloud", "aws", "azure", "devops", "kubernetes")),
    ("data", ("data", "analytics", "dataviz", "sql")),
    ("open-source", ("open-source", "opensource", "github")),
    ("design", ("design", "ui", "ux", "photography", "product-design")),
    ("startups", ("startups", "startup", "product", "entrepreneurship", "pitch")),
    ("web-app", ("web", "app", "android", "flutter", "react", "frontend", "backend", "hackathons")),
    ("careers", ("careers", "placement", "internship", "resume", "public-speaking", "jobs")),
    ("cultural-music", ("music", "cultural", "dance", "arts", "culture")),
    ("sports", ("sports", "football", "cricket", "fitness")),
    ("volunteering", ("volunteering", "volunteer", "community", "ngo")),
]


def suggest(tags: list[str] | None, text: str = "") -> str | None:
    """A category for these tags (or free text), or None if nothing fits."""
    words = [t.lower() for t in (tags or [])] + [w.strip(".,:;!?()").lower() for w in text.split()]
    for slug, keys in KEYWORDS:
        if any(w in keys for w in words):
            return slug
    return None


def ensure_rows(db) -> None:
    """Create the category rows if missing (migrations do this; tests build tables directly)."""
    from ..models import Category

    have = {c for (c,) in db.query(Category.slug).all()}
    for i, (slug, name, emoji) in enumerate(CATEGORIES):
        if slug not in have:
            db.add(Category(slug=slug, name=name, emoji=emoji, sort_order=i))
    db.commit()


def with_counts(db, events) -> list[dict]:
    """Every category in display order with how many of `events` (upcoming, published) are in it."""
    from collections import Counter

    from ..models import Category

    counts = Counter(e.category_slug for e in events if e.category_slug)
    rows = db.query(Category).order_by(Category.sort_order).all()
    return [{"slug": c.slug, "name": c.name, "emoji": c.emoji, "count": counts.get(c.slug, 0)} for c in rows]
