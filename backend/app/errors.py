from typing import NoReturn

from fastapi import HTTPException


def fail(status: int, code: str, message: str) -> NoReturn:
    """Raise an API error with a specific machine-readable code (the app shows `message` as is)."""
    raise HTTPException(status, {"code": code, "message": message})
