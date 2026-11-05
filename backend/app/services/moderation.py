"""AI safety check for group chat messages. Rules in services/chat.py always run first; this adds an
AI opinion when GROQ_API_KEY is set (see services/llm.py). Without a key, or if the AI is slow, it allows."""


def check_message(text: str) -> str | None:
    """A reason to block the message, or None to allow it."""
    from . import llm

    verdict = llm.classify_message(text)
    if verdict and verdict.get("block"):
        return verdict.get("reason") or "That message breaks the chat rules, so it wasn't posted."
    return None
