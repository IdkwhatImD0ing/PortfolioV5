/**
 * GET /sect/music.json: the /sect music's track list (public/sect/audio/music.json, written by the
 * audio pipeline beside the MP3s), or an empty list when there is none yet. The page reads it from
 * here rather than straight from public/, so a missing file is an empty list, not a 404 the browser
 * logs as an error. Static: a production build reads the file once, at build time.
 */
import { readFile } from "node:fs/promises";
import path from "node:path";

export const dynamic = "force-static";

const EMPTY = { version: 1, tracks: {} };

export async function GET(): Promise<Response> {
  try {
    const text = await readFile(path.join(process.cwd(), "public", "sect", "audio", "music.json"), "utf8");
    return Response.json(JSON.parse(text) as unknown);
  } catch {
    return Response.json(EMPTY);
  }
}
