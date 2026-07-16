from __future__ import annotations

import logging
import re
from pathlib import Path
from time import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from worldbuilder_core.config import get_settings
from worldbuilder_core.models import Entity

logger = logging.getLogger(__name__)

_generated_asset_name = re.compile(r"^[a-z0-9_-]+-[0-9a-f]{12}\.(?:gif|jpe?g|png|webp)$")


def entity_asset_url(attributes: dict | None) -> str | None:
    value = attributes.get("image_url") if isinstance(attributes, dict) else None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if _asset_filename(normalized) else None


def world_asset_urls(session: Session, world_id: str) -> set[str]:
    attributes = session.scalars(select(Entity.attributes).where(Entity.world_id == world_id))
    return {url for item in attributes if (url := entity_asset_url(item))}


def cleanup_unreferenced_assets(session: Session, candidate_urls: set[str | None]) -> None:
    candidates = {url for url in candidate_urls if url and _asset_filename(url)}
    if not candidates:
        return
    referenced = {
        url
        for attributes in session.scalars(select(Entity.attributes))
        if (url := entity_asset_url(attributes))
    }
    for url in candidates - referenced:
        _delete_generated_asset(url)


def cleanup_stale_orphaned_assets(session: Session, *, minimum_age_seconds: int = 86_400) -> None:
    upload_dir = Path(get_settings().upload_dir).resolve()
    if not upload_dir.is_dir():
        return
    referenced_names = {
        filename
        for attributes in session.scalars(select(Entity.attributes))
        if (url := entity_asset_url(attributes)) and (filename := _asset_filename(url))
    }
    cutoff = time() - minimum_age_seconds
    for path in upload_dir.iterdir():
        if not path.is_file() or not _generated_asset_name.fullmatch(path.name) or path.name in referenced_names:
            continue
        try:
            if path.stat().st_mtime <= cutoff:
                path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove orphaned asset %s: %s", path.name, exc)


def _asset_filename(url: str) -> str | None:
    prefix = "/assets/"
    if not url.startswith(prefix):
        return None
    filename = url[len(prefix) :]
    return filename if _generated_asset_name.fullmatch(filename) else None


def _delete_generated_asset(url: str) -> None:
    filename = _asset_filename(url)
    if not filename:
        return
    upload_dir = Path(get_settings().upload_dir).resolve()
    target = (upload_dir / filename).resolve()
    if upload_dir not in target.parents:
        return
    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not remove unreferenced asset %s: %s", filename, exc)
