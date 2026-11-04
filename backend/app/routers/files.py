from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..seed.make_samples import POSTERS, TIMETABLES
from ..db import get_db
from ..services.uploads import load_file

router = APIRouter(tags=["files"])


@router.get("/files/{name}")
def get_file(name: str, db: Session = Depends(get_db)):
    """Poster images. Names are random; the files are re-encoded, EXIF-free copies kept in the database."""
    f = load_file(db, name)
    if f is None:
        raise HTTPException(404, "File not found.")
    return Response(f.data, media_type=f.content_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/samples/{kind}/{name}.png")
def sample_image(kind: str, name: str):
    folders = {"posters": POSTERS, "timetables": TIMETABLES}
    if not settings.is_dev or kind not in folders or not name.replace("_", "").isalnum():
        raise HTTPException(404, "File not found.")
    path = folders[kind] / "generated" / f"{name}.png"
    if not path.is_file():
        raise HTTPException(404, "File not found.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})
