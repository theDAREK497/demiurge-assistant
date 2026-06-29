import base64
import binascii
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from worldbuilder_core.config import get_settings
from worldbuilder_core.schemas import AssetUploadRequest, AssetUploadResponse

router = APIRouter(prefix="/assets", tags=["assets"])

ALLOWED_CONTENT_TYPES = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_ASSET_BYTES = 5 * 1024 * 1024


@router.post("", response_model=AssetUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_asset(payload: AssetUploadRequest) -> AssetUploadResponse:
    extension = ALLOWED_CONTENT_TYPES.get(payload.content_type.lower())
    if extension is None:
        raise HTTPException(status_code=415, detail="Only PNG, JPEG, GIF, and WebP images are supported")

    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid base64 content") from exc

    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(content) > MAX_ASSET_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file is larger than 5 MB")

    upload_dir = Path(get_settings().upload_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    stem = _safe_stem(Path(payload.filename).stem)
    stored_filename = f"{stem}-{uuid4().hex[:12]}{extension}"
    target = (upload_dir / stored_filename).resolve()
    if upload_dir not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid upload path")

    target.write_bytes(content)
    return AssetUploadResponse(
        url=f"/assets/{stored_filename}",
        filename=stored_filename,
        size_bytes=len(content),
    )


def _safe_stem(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-_").lower()
    return normalized[:80] or "asset"
