"""Supabase Storage REST helper for clips, frames, audio, and datasets buckets."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _headers(service_key: str, content_type: str | None = None) -> dict[str, str]:
    hdr = {"Authorization": f"Bearer {service_key}", "apikey": service_key}
    if content_type:
        hdr["Content-Type"] = content_type
    return hdr


async def ensure_bucket(supabase_url: str, service_key: str, bucket: str) -> None:
    """Create a storage bucket if it does not already exist (idempotent)."""
    if not supabase_url or not service_key:
        return
    url = f"{supabase_url.rstrip('/')}/storage/v1/bucket"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            url,
            headers=_headers(service_key, "application/json"),
            json={"id": bucket, "name": bucket, "public": False},
        )
        if resp.status_code not in (200, 201, 409):
            logger.debug("ensure_bucket(%s) returned %s", bucket, resp.status_code)


async def upload_bytes(
    *,
    supabase_url: str,
    service_key: str,
    bucket: str,
    path: str,
    data: bytes,
    content_type: str,
) -> bool:
    """Upload raw bytes to Supabase Storage with x-upsert=true."""
    if not supabase_url or not service_key:
        return False
    clean_path = path.lstrip("/")
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{clean_path}"
    hdr = _headers(service_key, content_type)
    hdr["x-upsert"] = "true"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=hdr, content=data)
            if resp.status_code == 404 or (
                resp.status_code == 400 and "Bucket not found" in resp.text
            ):
                await ensure_bucket(supabase_url, service_key, bucket)
                resp = await client.post(url, headers=hdr, content=data)
            return resp.status_code in (200, 201)
    except Exception as exc:
        logger.debug("upload_bytes(%s/%s) failed: %s", bucket, clean_path, exc)
        return False


async def download_bytes(
    *, supabase_url: str, service_key: str, bucket: str, path: str
) -> bytes | None:
    """Download raw bytes from Supabase Storage, returning None if absent."""
    if not supabase_url or not service_key or not path:
        return None
    clean_path = path.lstrip("/")
    if clean_path.startswith(f"{bucket}/"):
        clean_path = clean_path.removeprefix(f"{bucket}/")
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{clean_path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=_headers(service_key))
            if resp.status_code == 200:
                return bytes(resp.content)
    except Exception as exc:
        logger.debug("download_bytes(%s/%s) failed: %s", bucket, clean_path, exc)
    return None


def _resolve_signed_url(supabase_url: str, rel: object) -> str | None:
    if not isinstance(rel, str):
        return None
    if rel.startswith("http"):
        return rel
    return f"{supabase_url.rstrip('/')}/storage/v1{rel}"


async def create_signed_upload_url(
    *, supabase_url: str, service_key: str, bucket: str, path: str
) -> str | None:
    """Create a Supabase Storage signed upload URL when configured."""
    if not supabase_url or not service_key:
        return None
    clean_path = path.lstrip("/")
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/upload/sign/{bucket}/{clean_path}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url, headers=_headers(service_key, "application/json"), json={}
            )
            if resp.status_code in (400, 404):
                await ensure_bucket(supabase_url, service_key, bucket)
                resp = await client.post(
                    url, headers=_headers(service_key, "application/json"), json={}
                )
            if resp.status_code in (200, 201):
                data: dict[str, Any] = resp.json()
                return _resolve_signed_url(supabase_url, data.get("url") or data.get("signedURL"))
    except Exception as exc:
        logger.debug("create_signed_upload_url failed: %s", exc)
    return None


async def create_signed_download_url(
    *, supabase_url: str, service_key: str, bucket: str, path: str, expires_in: int = 600
) -> str | None:
    """Create a Supabase Storage signed download URL for private objects."""
    if not supabase_url or not service_key or not path:
        return None
    clean_path = path.lstrip("/")
    if clean_path.startswith(f"{bucket}/"):
        clean_path = clean_path.removeprefix(f"{bucket}/")
    url = f"{supabase_url.rstrip('/')}/storage/v1/object/sign/{bucket}/{clean_path}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                headers=_headers(service_key, "application/json"),
                json={"expiresIn": expires_in},
            )
            if resp.status_code in (200, 201):
                data: dict[str, Any] = resp.json()
                return _resolve_signed_url(supabase_url, data.get("signedURL"))
    except Exception as exc:
        logger.debug("create_signed_download_url failed: %s", exc)
    return None
