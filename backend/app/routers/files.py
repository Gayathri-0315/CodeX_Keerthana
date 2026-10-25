from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..seed.make_samples import POSTERS, TIMETABLES
from ..services.uploads import file_path

router = APIRouter(tags=["files"])


@router.get("/files/{name}")
def get_file(name: str):
    """Poster images. Names are random, re-encoded, EXIF-free copies stored outside the web root."""
    path = file_path(name)
    if path is None:
        raise HTTPException(404, "File not found.")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/samples/{kind}/{name}.png")
def sample_image(kind: str, name: str):
    folders = {"posters": POSTERS, "timetables": TIMETABLES}
    if not settings.demo_mode or kind not in folders or not name.replace("_", "").isalnum():
        raise HTTPException(404, "File not found.")
    path = folders[kind] / "generated" / f"{name}.png"
    if not path.is_file():
        raise HTTPException(404, "File not found.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})
