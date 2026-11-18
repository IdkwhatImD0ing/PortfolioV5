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

## When the flight loads a track

Since 2026-11-17 the first tracks load before the visitor's first press, so that press plays at once.
Before, nothing downloaded until the press, and the first note came 0.8 to 1.5 seconds later on a
fast desktop.

- The track list is asked for when the page opens.
- With sound on (the default), the loading screen's track downloads as soon as the list is here.
  The opening place's track follows once the scene has loaded.
- Both are decoded before any press. The playing `AudioContext` may only be made inside a press, so
  an `OfflineAudioContext` at the files' sample rate does the decoding until then. It never plays
  anything.
- Nothing loads ahead for a visitor who muted, in a tab that is not in view, or in the page view.
- While the scene itself is downloading only one track loads, so the scene keeps the line.
- After the first press it is as before: the current track and the next one along the flight, one
  download at a time.
- A press on Enter goes straight to the opening place's song. The loading screen's song does not
  start for a moment first.
- A track that comes in out of silence fades in over 0.8 seconds. One that replaces a playing track
  still crossfades over 2.5 seconds.

## What the browser keeps

The backend sleeps when nobody has called it for about 15 minutes. On 2026-11-17 its first answer
after a sleep took 16.1 seconds. So the page keeps what it needs to play without it:

- The track list from the last visit, in `localStorage` under `sect.music.manifest`.
- Every track it has downloaded, in Cache Storage under `sect-music-v1`. An entry is named by the
  track's key, revision and size. All twelve tracks come to about 49 MB.

On the next visit the kept list is used at once, and the backend's list replaces it when it arrives.
A kept track plays with no request to the backend. A track whose revision, size or length changed in
the new list is downloaded again, and kept tracks the list no longer names are deleted. A browser
without Cache Storage, or with storage blocked, downloads every track as before.

Lyrics are not kept: they come from the backend each time. The `/music` page does not use the kept
tracks. A first-time visitor who arrives while the backend sleeps still waits for it.

To check it without sound, open the flight with `?debug=1` on a profile that has not muted, and do
not click, tap or press a key: nothing can play before a press. `window.__sectMusic.state()` lists
the decoded tracks under `buffers` while `context` is still `"none"`. Set
`localStorage["sect.music.muted"] = "1"` when done.

## Deterrence boundary

Private storage, opaque object names and short-lived capabilities remove permanent static asset URLs
and discourage hotlinking. They are not DRM: a browser must receive the audio and lyric data it
plays or renders, so a determined visitor can capture it.

The kept tracks are the same bytes the page was sent, in a store only this site can read. They do
sit on the visitor's disk, and DevTools can list them. The HTTP responses are still `no-store`.

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
