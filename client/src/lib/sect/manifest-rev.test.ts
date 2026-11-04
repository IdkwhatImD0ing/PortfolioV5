import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { fetchUrl, parseManifest, resolveAsset } from "./parse";

describe("manifest revisions (rev)", () => {
  const base = {
    version: 2,
    camera: "camera.json",
    meta: "meta.json",
    global: ["backdrop.glb.gz"],
    chunks: [{ id: "gate", files: ["gate.glb.gz"], filesLow: ["low/gate.glb.gz"], need: [1, 190] }],
  };

  it("reads rev, dropping entries that are not fingerprints", () => {
    const m = parseManifest({ ...base, rev: { "gate.glb.gz": "0123456789abcdef", bad: 5, empty: "" } });
    expect(m.rev).toEqual({ "gate.glb.gz": "0123456789abcdef" });
  });

  it("has no rev when the manifest has none", () => {
    expect("rev" in parseManifest(base)).toBe(false);
    expect("rev" in parseManifest({ ...base, rev: {} })).toBe(false);
  });

  it("adds ?v= only to a file that has a rev", () => {
    const rev = { "gate.glb.gz": "0123456789abcdef" };
    expect(fetchUrl("/sect/full", "gate.glb.gz", rev)).toBe("/sect/full/gate.glb.gz?v=0123456789abcdef");
    expect(fetchUrl("/sect/full", "low/gate.glb.gz", rev)).toBe("/sect/full/low/gate.glb.gz");
    expect(fetchUrl("/sect/full", "gate.glb.gz")).toBe(resolveAsset("/sect/full", "gate.glb.gz"));
    expect(fetchUrl("/sect/full", "manifest.json", rev)).toBe("/sect/full/manifest.json");
  });
});

const fullDir = join(__dirname, "../../../public/sect/full");
describe.skipIf(!existsSync(join(fullDir, "manifest.json")))("the published full manifest's rev", () => {
  it("covers every file the manifest lists, with 16 hex characters each", () => {
    const manifest = parseManifest(JSON.parse(readFileSync(join(fullDir, "manifest.json"), "utf8")));
    const listed = [manifest.camera, manifest.meta, manifest.clouds, manifest.flyer, manifest.flyerPath, manifest.detail, manifest.water, ...manifest.global, ...(manifest.globalLow ?? [])];
    for (const c of manifest.chunks) listed.push(...c.files, ...(c.filesLow ?? []));
    const files = listed.filter((f): f is string => typeof f === "string");
    expect(files.length).toBeGreaterThan(10);
    for (const f of files) expect(manifest.rev?.[f], f).toMatch(/^[0-9a-f]{16}$/);
    expect(manifest.rev?.["manifest.json"]).toBeUndefined();
  });

  it("matches the bytes on disk, so a changed file cannot ship under an old ?v= URL", () => {
    const manifest = JSON.parse(readFileSync(join(fullDir, "manifest.json"), "utf8")) as { rev?: Record<string, string> };
    for (const [f, r] of Object.entries(manifest.rev ?? {})) {
      let b = readFileSync(join(fullDir, f));
      let h: string;
      if (b.subarray(0, 64).toString("latin1").startsWith("version https://git-lfs")) {
        // a Git LFS pointer: its oid is the sha256 of the real file
        h = /oid sha256:([0-9a-f]{64})/.exec(b.toString("latin1"))![1].slice(0, 16);
      } else {
        // JSON is hashed with LF line endings, as git stores it and the host serves it
        if (f.endsWith(".json")) b = Buffer.from(b.toString("latin1").replace(/\r\n/g, "\n"), "latin1");
        h = createHash("sha256").update(b).digest("hex").slice(0, 16);
      }
      expect(h, `${f}: file changed but manifest.json rev not updated (rerun sect_pack.py or update rev)`).toBe(r);
    }
  });
});
