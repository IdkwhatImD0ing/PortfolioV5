import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import music


ORIGIN = "https://www.art3m1s.me"
REVISION = "0123456789abcdef"


@pytest.fixture
def music_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    storage = tmp_path / "storage"
    audio = storage / f"audio/gate-{REVISION}.mp3"
    lyrics = storage / f"lyrics/gate-{REVISION}.json"
    audio.parent.mkdir(parents=True)
    lyrics.parent.mkdir(parents=True)
    audio.write_bytes(b"0123456789")
    lyrics.write_text('{"song":"test"}', encoding="utf-8")
    manifest = {
        "version": 2,
        "tracks": {
            "gate": {
                "sourceId": "source",
                "title": "Test",
                "artist": "Test Artist",
                "show": "Show",
                "language": "zh",
                "audioObject": f"audio/gate-{REVISION}.mp3",
                "lyricsObject": f"lyrics/gate-{REVISION}.json",
                "duration": 10,
                "loopStart": 0,
                "loopEnd": 10,
                "bpm": None,
                "lufs": -17,
                "bytes": 10,
                "audioSha256": "secret-internal-hash",
                "revision": REVISION,
            },
            "loading": {
                "title": "Instrumental",
                "artist": "Test Artist",
                "show": "Show",
                "language": None,
                "audioObject": f"audio/gate-{REVISION}.mp3",
                "lyricsObject": None,
                "duration": 10,
                "loopStart": 0,
                "loopEnd": 10,
                "bytes": 10,
                "revision": REVISION,
            },
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(music, "MANIFEST_PATH", manifest_path)
    monkeypatch.setenv("MUSIC_STORAGE_DIR", str(storage))
    monkeypatch.setenv("MUSIC_SIGNING_SECRET", "test-signing-secret")
    app = FastAPI()
    app.include_router(music.router)
    return TestClient(app)


def capability(client: TestClient, key: str = "gate", resource: str = "audio") -> str:
    response = client.post(f"/music/access/{key}/{resource}", headers={"Origin": ORIGIN})
    assert response.status_code == 200
    return response.json()["token"]


def auth(token: str) -> dict[str, str]:
    return {"Origin": ORIGIN, "Authorization": f"Bearer {token}"}


def test_public_manifest_contains_metadata_but_no_storage_details(music_client: TestClient):
    response = music_client.get("/music/manifest")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    track = response.json()["tracks"]["gate"]
    assert track["hasLyrics"] is True
    assert track["artist"] == "Test Artist"
    assert track["revision"] == REVISION
    assert "audioObject" not in track
    assert "lyricsObject" not in track
    assert "sourceId" not in track
    assert "audioSha256" not in track


@pytest.mark.parametrize("origin", [None, "https://evil.example", "http://art3m1s.me"])
def test_capabilities_require_an_allowed_origin(music_client: TestClient, origin: str | None):
    headers = {"Origin": origin} if origin else {}
    assert music_client.post("/music/access/gate/audio", headers=headers).status_code == 403


def test_configured_origin_and_subdomains_are_allowed(music_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    assert music_client.post("/music/access/gate/audio", headers={"Origin": "https://portfolio.art3m1s.me"}).status_code == 200
    monkeypatch.setenv("MUSIC_ALLOWED_ORIGINS", "https://preview.example")
    assert music_client.post("/music/access/gate/audio", headers={"Origin": "https://preview.example"}).status_code == 200


def test_instrumental_has_no_lyrics_capability(music_client: TestClient):
    assert music_client.post("/music/access/loading/lyrics", headers={"Origin": ORIGIN}).status_code == 404


def test_tokens_are_required_and_bound_to_track_and_resource(music_client: TestClient):
    audio_token = capability(music_client)
    lyrics_token = capability(music_client, resource="lyrics")
    assert music_client.get("/music/tracks/gate", headers={"Origin": ORIGIN}).status_code == 401
    assert music_client.get("/music/tracks/gate", headers=auth("malformed")).status_code == 401
    assert music_client.get("/music/lyrics/gate", headers=auth(audio_token)).status_code == 401
    assert music_client.get("/music/tracks/loading", headers=auth(audio_token)).status_code == 401
    assert music_client.get("/music/lyrics/gate", headers=auth(lyrics_token)).status_code == 200


def test_expired_token_is_rejected(music_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    token = capability(music_client)
    monkeypatch.setattr(music, "TOKEN_TTL_SECONDS", -1)
    assert music_client.get("/music/tracks/gate", headers=auth(token)).status_code == 401


def test_full_and_partial_byte_ranges(music_client: TestClient):
    token = capability(music_client)
    response = music_client.get("/music/tracks/gate", headers=auth(token))
    assert response.status_code == 200
    assert response.content == b"0123456789"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "10"

    for range_value, expected, content_range in [
        ("bytes=2-5", b"2345", "bytes 2-5/10"),
        ("bytes=7-", b"789", "bytes 7-9/10"),
        ("bytes=-3", b"789", "bytes 7-9/10"),
        ("bytes=0-999", b"0123456789", "bytes 0-9/10"),
    ]:
        response = music_client.get("/music/tracks/gate", headers={**auth(token), "Range": range_value})
        assert response.status_code == 206
        assert response.content == expected
        assert response.headers["content-range"] == content_range


@pytest.mark.parametrize("range_value", ["items=0-1", "bytes=10-", "bytes=3-2", "bytes=-0", "bytes=0-1,3-4"])
def test_invalid_ranges_return_416(music_client: TestClient, range_value: str):
    response = music_client.get(
        "/music/tracks/gate",
        headers={**auth(capability(music_client)), "Range": range_value},
    )
    assert response.status_code == 416
    assert response.headers["content-range"] == "bytes */10"


def test_lyrics_are_private_and_have_a_known_length(music_client: TestClient):
    response = music_client.get("/music/lyrics/gate", headers=auth(capability(music_client, resource="lyrics")))
    assert response.status_code == 200
    assert response.json() == {"song": "test"}
    assert response.headers["content-length"] == str(len(response.content))
    assert response.headers["cache-control"] == "private, no-store"


def test_missing_mismatched_and_invalid_objects_fail_before_streaming(
    music_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    token = capability(music_client)
    storage = Path(music.os.environ["MUSIC_STORAGE_DIR"])
    audio = storage / f"audio/gate-{REVISION}.mp3"
    audio.unlink()
    assert music_client.get("/music/tracks/gate", headers=auth(token)).status_code == 404
    audio.write_bytes(b"short")
    assert music_client.get("/music/tracks/gate", headers=auth(token)).status_code == 503
    manifest = music._manifest()
    manifest["tracks"]["gate"]["audioObject"] = "../escape.mp3"
    bad_path = Path(music.MANIFEST_PATH)
    bad_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert music_client.get("/music/tracks/gate", headers=auth(token)).status_code == 404
