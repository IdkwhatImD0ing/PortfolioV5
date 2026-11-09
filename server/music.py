"""Private soundtrack manifest, capabilities, lyrics and byte-range audio."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


router = APIRouter(prefix="/music", tags=["music"])
MANIFEST_PATH = Path(__file__).with_name("music_manifest.json")
TOKEN_TTL_SECONDS = 90
CHUNK_BYTES = 256 * 1024
ORIGIN_PATTERN = re.compile(r"^https://([a-z0-9-]+\.)*art3m1s\.me$")
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
OBJECT_PATTERN = re.compile(
    r"^(audio/[a-z][a-z0-9-]*-[a-f0-9]{16}\.mp3|lyrics/[a-z][a-z0-9-]*-[a-f0-9]{16}\.json)$"
)
Resource = Literal["audio", "lyrics"]
logger = logging.getLogger(__name__)


def _manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 2, "tracks": {}}
    if (
        not isinstance(value, dict)
        or value.get("version") != 2
        or not isinstance(value.get("tracks"), dict)
    ):
        return {"version": 2, "tracks": {}}
    return value


def _track(key: str) -> dict[str, Any]:
    if not KEY_PATTERN.fullmatch(key):
        raise HTTPException(status_code=404, detail="Track not found")
    value = _manifest()["tracks"].get(key)
    if not isinstance(value, dict):
        raise HTTPException(status_code=404, detail="Track not found")
    return value


def _allowed_origin(origin: str | None) -> bool:
    if origin == "http://localhost:3000" or (
        origin is not None and ORIGIN_PATTERN.fullmatch(origin)
    ):
        return True
    configured = {
        item.strip()
        for item in os.getenv("MUSIC_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    return origin in configured


def _require_origin(request: Request) -> None:
    if not _allowed_origin(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origin not allowed")


def _serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("MUSIC_SIGNING_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="Music is not configured")
    return URLSafeTimedSerializer(secret, salt="sect-music-v1")


def _token_payload(token: str, key: str, resource: Resource) -> None:
    try:
        payload = _serializer().loads(token, max_age=TOKEN_TTL_SECONDS)
    except SignatureExpired as exc:
        raise HTTPException(status_code=401, detail="Capability expired") from exc
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail="Invalid capability") from exc
    if payload != {"key": key, "resource": resource}:
        raise HTTPException(status_code=401, detail="Invalid capability")


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing capability")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing capability")
    return token


def _public_track(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": track.get("title"),
        "artist": track.get("artist"),
        "show": track.get("show"),
        "language": track.get("language"),
        "hasLyrics": bool(track.get("lyricsObject")),
        "duration": track.get("duration"),
        "loopStart": track.get("loopStart"),
        "loopEnd": track.get("loopEnd"),
        "bpm": track.get("bpm"),
        "lufs": track.get("lufs"),
        "bytes": track.get("bytes"),
        "revision": track.get("revision"),
    }


@router.get("/manifest")
def music_manifest() -> JSONResponse:
    manifest = _manifest()
    return JSONResponse(
        {
            "version": 2,
            "tracks": {
                key: _public_track(track)
                for key, track in manifest["tracks"].items()
                if KEY_PATTERN.fullmatch(key) and isinstance(track, dict)
            },
        },
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/access/{key}/{resource}")
def music_access(
    key: str, resource: Resource, request: Request
) -> dict[str, str | int]:
    _require_origin(request)
    track = _track(key)
    if resource == "lyrics" and not track.get("lyricsObject"):
        raise HTTPException(status_code=404, detail="Lyrics not found")
    token = _serializer().dumps({"key": key, "resource": resource})
    return {"token": token, "expiresIn": TOKEN_TTL_SECONDS}


def _range(value: str | None, size: int) -> tuple[int, int, bool]:
    def invalid() -> HTTPException:
        return HTTPException(
            status_code=416,
            detail="Invalid range",
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    if not value:
        return 0, size - 1, False
    if not value.startswith("bytes=") or "," in value:
        raise invalid()
    raw = value[6:]
    if "-" not in raw:
        raise invalid()
    left, right = raw.split("-", 1)
    try:
        if left:
            start = int(left)
            end = min(int(right), size - 1) if right else size - 1
        else:
            suffix = int(right)
            if suffix <= 0:
                raise ValueError
            start = max(0, size - suffix)
            end = size - 1
    except ValueError as exc:
        raise invalid() from exc
    if start < 0 or start >= size or end < start:
        raise invalid()
    return start, end, True


def _local_chunks(path: Path, start: int, length: int) -> Iterator[bytes]:
    try:
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                block = handle.read(min(CHUNK_BYTES, remaining))
                if not block:
                    break
                remaining -= len(block)
                yield block
    except OSError:
        logger.error("Local music stream failed")


def _gcs_chunks(object_name: str, start: int, length: int) -> Iterator[bytes]:
    try:
        from google.cloud import storage

        bucket_name = os.environ["MUSIC_BUCKET"]
        blob = storage.Client().bucket(bucket_name).blob(object_name)
        with blob.open("rb", chunk_size=CHUNK_BYTES) as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                block = handle.read(min(CHUNK_BYTES, remaining))
                if not block:
                    break
                remaining -= len(block)
                yield block
    except Exception:
        # The response has already started by the time a generator fails. Do not
        # leak bucket or object details into the response body.
        logger.error("Cloud music stream failed")


def _object_path(object_name: str) -> Path | None:
    if not OBJECT_PATTERN.fullmatch(object_name):
        raise HTTPException(status_code=404, detail="Media not found")
    local = os.getenv("MUSIC_STORAGE_DIR")
    if not local:
        return None
    base = Path(local).resolve()
    candidate = (base / object_name).resolve()
    if base not in candidate.parents:
        raise HTTPException(status_code=404, detail="Media not found")
    return candidate


def _object_size(object_name: str) -> int:
    path = _object_path(object_name)
    if path is not None:
        try:
            if not path.is_file():
                raise HTTPException(status_code=404, detail="Media not found")
            return path.stat().st_size
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Media temporarily unavailable") from exc
    try:
        from google.api_core.exceptions import GoogleAPICallError, NotFound
        from google.cloud import storage

        bucket_name = os.getenv("MUSIC_BUCKET")
        if not bucket_name:
            raise HTTPException(status_code=503, detail="Music is not configured")
        blob = storage.Client().bucket(bucket_name).blob(object_name)
        blob.reload()
        if not isinstance(blob.size, int):
            raise HTTPException(status_code=503, detail="Media temporarily unavailable")
        return blob.size
    except HTTPException:
        raise
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Media not found") from exc
    except GoogleAPICallError as exc:
        raise HTTPException(status_code=503, detail="Media temporarily unavailable") from exc


def _chunks(object_name: str, start: int, length: int) -> Iterator[bytes]:
    candidate = _object_path(object_name)
    if candidate is not None:
        return _local_chunks(candidate, start, length)
    return _gcs_chunks(object_name, start, length)


@router.get("/tracks/{key}")
def music_track(
    key: str,
    request: Request,
    authorization: str | None = Header(default=None),
    range_header: str | None = Header(default=None, alias="Range"),
) -> StreamingResponse:
    _require_origin(request)
    _token_payload(_bearer(authorization), key, "audio")
    track = _track(key)
    size = track.get("bytes")
    object_name = track.get("audioObject")
    if not isinstance(size, int) or size <= 0 or not isinstance(object_name, str):
        raise HTTPException(status_code=404, detail="Track not found")
    if _object_size(object_name) != size:
        raise HTTPException(status_code=503, detail="Media temporarily unavailable")
    start, end, partial = _range(range_header, size)
    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Disposition": "inline",
        "Cache-Control": "private, no-store",
        "Vary": "Origin",
    }
    if partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(
        _chunks(object_name, start, length),
        status_code=206 if partial else 200,
        media_type="audio/mpeg",
        headers=headers,
    )


@router.get("/lyrics/{key}")
def music_lyrics(
    key: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    _require_origin(request)
    _token_payload(_bearer(authorization), key, "lyrics")
    track = _track(key)
    object_name = track.get("lyricsObject")
    if not isinstance(object_name, str):
        raise HTTPException(status_code=404, detail="Lyrics not found")
    size = _object_size(object_name)
    return StreamingResponse(
        _chunks(object_name, 0, size),
        media_type="application/json",
        headers={
            "Content-Length": str(size),
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
            "Vary": "Origin",
        },
    )
