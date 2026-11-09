#!/usr/bin/env python3
"""Prepare and publish the sect soundtrack.

`prepare` discovers the handoff by source id, validates lyrics, normalizes every
MP3, writes hash-named objects under server/.music-prepared and installs the
metadata-only server/music_manifest.json.

`upload` copies those immutable objects to MUSIC_BUCKET. It is deliberately a
separate command so a backend deploy never changes media.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(
    r"E:\Github\personal\youtube-mp3-downloader\downloads\website-music"
)
DEFAULT_OUTPUT = ROOT / ".music-prepared"
MANIFEST_PATH = ROOT / "music_manifest.json"
SOUNDTRACK_REVISION = "20261108-1"
ID_PATTERN = re.compile(r"\[([A-Za-z0-9_-]{11})\]\.mp3$")


@dataclass(frozen=True)
class TrackSpec:
    key: str
    source_id: str
    title: str
    show: str
    artist: str
    language: str | None = None


TRACKS = (
    TrackSpec("loading", "jbF369bXcJU", "风舞", "斗罗大陆", "Not credited"),
    TrackSpec("gate", "nd9Sdcv5egM", "铁血丹心", "射雕英雄传 2017", "Not credited"),
    TrackSpec("mirror", "3eSajcF8_Fw", "Throne of Glory", "神印王座", "Xian Ke", "en"),
    TrackSpec("forge", "eiquXgRDa40", "刀剑如梦", "倚天屠龙记 2019", "Instrumental ensemble"),
    TrackSpec("arena", "n7w5How-ALE", "降临", "神印王座", "Qi You (祁游)", "zh"),
    TrackSpec("mission", "gUPnXFn-33w", "璀璨冒险人", "斗罗大陆2", "Zhou Shen (周深)", "zh"),
    TrackSpec("library", "r2a-1S3xNQY", "化凡", "仙逆", "Yang Zixi (杨子熙)", "zh"),
    TrackSpec("steles", "jFXCp-kc4h8", "光之少年", "神印王座", "GALA", "zh"),
    TrackSpec("scroll", "i2CER52gUVc", "浩瀚", "神雕侠侣 2014", "Zhang Jie (张杰)", "zh"),
    TrackSpec("formation", "ll17o0KFV-Q", "天谴觉醒", "神印王座", "Not credited"),
    TrackSpec("abode", "dQONNl1YOeY", "逍遥", "笑傲江湖 2013", "Wallace Huo (霍建华)", "zh"),
    TrackSpec("summit", "TjvrbPqfBxI", "破茧", "斗罗大陆", "Angela Zhang (张韶涵)", "zh"),
)


def fail(message: str) -> "NoReturn":
    raise SystemExit(message)


def run(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        fail(f"Required command is not installed: {command[0]}")
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip()
        fail(f"{command[0]} failed: {detail}")
    return result.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path) -> dict[str, Any]:
    output = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,bit_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    data = json.loads(output)["format"]
    return {
        "duration": round(float(data["duration"]), 6),
        "bitRate": int(data["bit_rate"]),
        "bytes": path.stat().st_size,
    }


def discover_mp3s(source: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in source.glob("*.mp3"):
        match = ID_PATTERN.search(path.name)
        if not match:
            continue
        source_id = match.group(1)
        if source_id in found:
            fail(f"Duplicate MP3 source id: {source_id}")
        found[source_id] = path
    expected = {track.source_id for track in TRACKS}
    if set(found) != expected:
        missing = sorted(expected - set(found))
        extra = sorted(set(found) - expected)
        fail(f"MP3 handoff mismatch; missing={missing}, extra={extra}")
    return found


def number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if result >= 0 else None


def validate_lyrics(path: Path, spec: TrackSpec) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("id") != spec.source_id:
        fail(f"{path.name}: id does not match {spec.source_id}")
    if data.get("song") != spec.title or data.get("show") != spec.show:
        fail(f"{path.name}: song/show metadata does not match the soundtrack map")
    if data.get("language") != spec.language:
        fail(f"{path.name}: language does not match {spec.language}")
    lines = data.get("lines")
    if not isinstance(lines, list) or not lines:
        fail(f"{path.name}: lines must be a non-empty list")
    previous_end = 0.0
    for line_index, line in enumerate(lines):
        if not isinstance(line, dict):
            fail(f"{path.name}: line {line_index} is not an object")
        start = number(line.get("start"))
        end = number(line.get("end"))
        text = line.get("text")
        words = line.get("words")
        if (
            start is None
            or end is None
            or end < start
            or start < previous_end
            or not isinstance(text, str)
            or not isinstance(words, list)
        ):
            fail(f"{path.name}: invalid line {line_index}")
        joined: list[str] = []
        word_end = start
        for word_index, word in enumerate(words):
            if not isinstance(word, dict) or not isinstance(word.get("w"), str):
                fail(f"{path.name}: invalid word {line_index}:{word_index}")
            word_start = number(word.get("start"))
            next_end = number(word.get("end"))
            if (
                word_start is None
                or next_end is None
                or word_start < start
                or next_end > end
                or next_end < word_start
                or word_start < word_end
            ):
                fail(f"{path.name}: invalid word timing {line_index}:{word_index}")
            joined.append(word["w"])
            word_end = next_end
        if "".join(joined) != text:
            fail(f"{path.name}: words do not reconstruct line {line_index}")
        previous_end = end
    # Ship only fields the karaoke renderer needs. Source IDs, local filenames
    # and source URLs stay in the handoff folder.
    return {
        "song": data["song"],
        "show": data["show"],
        "language": data["language"],
        "lines": data["lines"],
    }


def normalize(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-vn",
            "-af",
            "loudnorm=I=-17:TP=-1.5:LRA=11",
            "-ar",
            "48000",
            "-b:a",
            "160k",
            "-map_metadata",
            "-1",
            str(target),
        ]
    )


def prepare(source: Path, output: Path) -> None:
    if not source.is_dir():
        fail(f"Source folder does not exist: {source}")
    mp3s = discover_mp3s(source)
    lyric_dir = source / "lyrics"
    expected_lyrics = {track.source_id for track in TRACKS if track.language}
    actual_lyrics = {
        path.stem for path in lyric_dir.glob("*.json") if path.name != "manifest.json"
    }
    if actual_lyrics != expected_lyrics:
        fail(
            "Lyric handoff mismatch; "
            f"missing={sorted(expected_lyrics - actual_lyrics)}, "
            f"extra={sorted(actual_lyrics - expected_lyrics)}"
        )
    if output.exists():
        shutil.rmtree(output)
    (output / "audio").mkdir(parents=True)
    (output / "lyrics").mkdir(parents=True)

    manifest: dict[str, Any] = {"version": 2, "tracks": {}}
    for spec in TRACKS:
        temporary = output / "audio" / f"{spec.key}.mp3"
        normalize(mp3s[spec.source_id], temporary)
        audio_hash = sha256(temporary)
        audio_name = f"{spec.key}-{audio_hash[:16]}.mp3"
        audio_path = temporary.with_name(audio_name)
        temporary.rename(audio_path)
        audio = probe(audio_path)
        duration = audio["duration"]

        lyric_object = None
        lyric_hash = None
        if spec.language:
            lyrics = validate_lyrics(lyric_dir / f"{spec.source_id}.json", spec)
            encoded = (
                json.dumps(lyrics, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            lyric_hash = hashlib.sha256(encoded).hexdigest()
            lyric_name = f"{spec.key}-{lyric_hash[:16]}.json"
            lyric_path = output / "lyrics" / lyric_name
            lyric_path.write_bytes(encoded)
            lyric_object = f"lyrics/{lyric_name}"

        manifest["tracks"][spec.key] = {
            "sourceId": spec.source_id,
            "title": spec.title,
            "show": spec.show,
            "artist": spec.artist,
            "language": spec.language,
            "audioObject": f"audio/{audio_name}",
            "lyricsObject": lyric_object,
            "duration": duration,
            "loopStart": 0 if spec.language else 0.3,
            "loopEnd": round(duration if spec.language else max(1.0, duration - 0.3), 6),
            "bpm": None,
            "lufs": -17.0,
            "bytes": audio["bytes"],
            "audioSha256": audio_hash,
            "lyricsSha256": lyric_hash,
            "revision": SOUNDTRACK_REVISION,
        }
        print(f"prepared {spec.key:9} {duration:8.3f}s {audio['bytes']:9d} bytes")

    encoded_manifest = json.dumps(
        manifest, ensure_ascii=False, indent=2, sort_keys=False
    ) + "\n"
    (output / "music_manifest.json").write_text(
        encoded_manifest, encoding="utf-8"
    )
    MANIFEST_PATH.write_text(encoded_manifest, encoding="utf-8")
    print(f"wrote {MANIFEST_PATH}")
    print(f"prepared objects in {output}")


def upload(output: Path, bucket_name: str) -> None:
    try:
        from google.cloud import storage
    except ImportError:
        fail("google-cloud-storage is required for upload")
    manifest_path = output / "music_manifest.json"
    if not manifest_path.is_file():
        fail(f"Run prepare first; missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for track in manifest["tracks"].values():
        objects = (track["audioObject"], track.get("lyricsObject"))
        for object_name in objects:
            if not object_name:
                continue
            local = output / object_name
            blob = bucket.blob(object_name)
            content_type = (
                "audio/mpeg" if object_name.endswith(".mp3") else "application/json"
            )
            if blob.exists(client):
                print(f"exists   gs://{bucket_name}/{object_name}")
                continue
            blob.upload_from_filename(local, content_type=content_type)
            print(f"uploaded gs://{bucket_name}/{object_name}")
    print("Objects uploaded. Deploy the matching server/music_manifest.json.")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    publish = sub.add_parser("upload")
    publish.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    publish.add_argument("--bucket", default=os.getenv("MUSIC_BUCKET"))
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "prepare":
        prepare(args.source.resolve(), args.output.resolve())
        return
    if not args.bucket:
        fail("Set MUSIC_BUCKET or pass --bucket")
    upload(args.output.resolve(), args.bucket)


if __name__ == "__main__":
    main()
