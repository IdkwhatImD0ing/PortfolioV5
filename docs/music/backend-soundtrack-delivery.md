# Backend soundtrack delivery

The replacement soundtrack and timed lyrics are stored outside the frontend and delivered through
the FastAPI service.

## Storage

- Prepared MP3 and lyric JSON objects live in a private Google Cloud Storage bucket.
- Public Access Prevention and uniform bucket-level access stay enabled.
- The Cloud Run runtime service account receives only `storage.objectViewer`.
- Git, the frontend bundle and the backend container contain only metadata, never soundtrack files.
- Local development can use `MUSIC_STORAGE_DIR` instead of Cloud Storage.

## Request flow

1. The client requests the metadata-only music manifest, including title, artist, source show and
   vocal type, from FastAPI.
2. Before loading a track or its lyrics, the client asks for a short-lived capability for that
   music key and resource type.
3. FastAPI returns a signed capability lasting 90 seconds.
4. The client sends it in the `Authorization` header.
5. FastAPI validates the signature, expiry, origin, resource type and fixed music-key allowlist.
6. Audio is streamed from Cloud Storage. Lyrics are returned only for tracks that declare them;
   served lyric JSON is allowlisted to song, show, language, lines and timed words.

Capabilities never appear in query strings or logs.

## Audio response contract

The audio endpoint supports a full response and one HTTP byte range:

- Full file: `200`
- Valid range: `206` with `Content-Range`
- Invalid or unsatisfiable range: `416`
- Every successful audio response includes `Accept-Ranges`, `Content-Length`,
  `Content-Type: audio/mpeg` and `Content-Disposition: inline`.
- Audio and lyric responses use private, no-store caching.

The browser's Web Audio engine still decodes a complete track before playback. That keeps the
existing sample-accurate loop points, position restoration and equal-power crossfades. Range support
makes the endpoint standards-compliant and leaves room for a future media-element player.

## Deterrence boundary

Private storage, opaque object names and short-lived capabilities remove permanent static asset URLs
and discourage hotlinking. They are not DRM: a browser must receive the audio and lyric data it
plays or renders, so a determined visitor can capture it.

## Configuration

The server uses:

- `MUSIC_BUCKET`: production bucket name.
- `MUSIC_SIGNING_SECRET`: capability signing secret.
- `MUSIC_STORAGE_DIR`: development-only local prepared-output folder.

Production startup requires the bucket and signing secret. Secret values, authorization headers and
opaque object names must not be logged.

Local development points `MUSIC_STORAGE_DIR` at `server/.music-prepared` and uses a local
`MUSIC_SIGNING_SECRET`. The browser resolves the same FastAPI endpoints it uses in production.

## Publish and rollback

Preparation and upload are separate commands. Publishing uploads immutable, hash-named objects, then
installs the metadata manifest. Backend deployment never uploads audio.

To roll back, restore the previous manifest revision. Immutable objects remain available until the
old manifest is no longer needed, then a separate cleanup command may remove unreferenced objects.
