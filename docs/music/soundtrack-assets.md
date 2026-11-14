# Prepared soundtrack assets

This is the release inventory generated from `server/music_manifest.json` for soundtrack revision
`20261108-1`. It records public playback metadata only; storage paths and hashes remain implementation
details.

All audio is MP3 at 48 kHz and 160 kbps, normalized to `-17 LUFS` with a `-1.5 dBTP` ceiling.

| Key | Song | Artist | Duration | Size | Lyrics | Loop |
|---|---|---|---:|---:|---|---|
| `loading` | 风舞 | Not credited | 1:27.059 | 1.74 MB | No | 0.300–1:26.759 |
| `gate` | 铁血丹心 | Not credited | 1:08.870 | 1.38 MB | No | 0.300–1:08.570 |
| `mirror` | Throne of Glory | Xian Ke | 3:50.869 | 4.62 MB | English | Full track |
| `forge` | 刀剑如梦 | Instrumental ensemble | 1:22.517 | 1.65 MB | No | 0.300–1:22.217 |
| `arena` | 降临 | Qi You (祁游) | 3:59.692 | 4.80 MB | Chinese + English | Full track |
| `mission` | 璀璨冒险人 | Zhou Shen (周深) | 4:33.726 | 5.48 MB | Chinese + English | Full track |
| `library` | 化凡 | Yang Zixi (杨子熙) | 4:26.635 | 5.33 MB | Chinese + English | Full track |
| `steles` | 光之少年 | GALA | 3:56.364 | 4.73 MB | Chinese + English | Full track |
| `scroll` | 浩瀚 | Zhang Jie (张杰) | 3:43.125 | 4.46 MB | Chinese + English | Full track |
| `formation` | 曙光 | Chen Bing (陈冰) | 4:05.569 | 4.91 MB | Chinese + English | Full track |
| `abode` | 逍遥 | Wallace Huo (霍建华) | 4:25.102 | 5.30 MB | Chinese + English | Full track |
| `summit` | 破茧 | Angela Zhang (张韶涵) | 3:31.522 | 4.23 MB | Chinese + English | Full track |

## Rebuild

From `server/`:

```bash
python scripts/prepare_music.py prepare
python scripts/prepare_music.py upload --bucket "$MUSIC_BUCKET"
```

`prepare` requires ffmpeg and ffprobe. It validates the exact twelve source IDs, validates all lyric
and word timings, strips private handoff metadata from the served lyric copies, normalizes audio,
writes immutable object names, and updates `server/music_manifest.json`. `upload` publishes the
prepared objects but does not deploy the server.

The handoff folder also keeps the retired 天谴觉醒 MP3 and a hidden sync marker in `lyrics\`.
`prepare` stops on either one, because it checks for exactly the twelve MP3s and nine lyric files.
Copy those twelve and nine to a clean folder and point `prepare` at it:

```bash
python scripts/prepare_music.py prepare --source <clean copy>
```

A change to lyrics alone gives the audio the same object names as before, so `upload` adds only the
new lyric files (checked on 2026-11-13 with ffmpeg 8.0.1).

After publishing, deploy the matching backend manifest before the frontend. Rollback restores the
previous backend revision and manifest; immutable media objects are retained until no rollback needs
them.
